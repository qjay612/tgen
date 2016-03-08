#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Extracting embeddings from DAs and trees (basically dictionaries with indexes).
"""

from __future__ import unicode_literals
from tgen.tree import TreeData, NodeData


class EmbeddingExtract(object):
    """Abstract ancestor of embedding extraction classes."""

    MIN_VALID = 4

    def __init__(self):
        pass

    def init_dict(self, train_data, dict_ord=None):
        """Initialize embedding dictionary (word -> id)."""
        raise NotImplementedError()

    def get_embeddings(self, data):
        """Get the embeddings of a data instance."""
        raise NotImplementedError()

    def get_embeddings_shape(self):
        """Return the shape of the embedding matrix (for one object, disregarding batches)."""
        raise NotImplementedError


class DAEmbeddingExtract(EmbeddingExtract):
    """Extracting embeddings for dialogue acts (currently, just slot-value list)."""

    UNK_SLOT = 0
    UNK_VALUE = 1

    def __init__(self, cfg):
        super(DAEmbeddingExtract, self).__init__()

        self.dict_slot = {'UNK_SLOT': self.UNK_SLOT}
        self.dict_value = {'UNK_VALUE': self.UNK_VALUE}
        self.max_da_len = cfg.get('max_da_len', 10)

    def init_dict(self, train_das, dict_ord=None):
        """Initialize dictionary, given training DAs (store slots and values,
        assign them IDs).

        @param train_das: training DAs
        @param dict_ord: lowest ID to be assigned (if None, it is initialized to MIN_VALID)
        @return: the highest ID assigned + 1 (the current lowest available ID)
        """

        if dict_ord is None:
            dict_ord = self.MIN_VALID

        for da in train_das:
            for dai in da:
                if dai.name not in self.dict_slot:
                    self.dict_slot[dai.name] = dict_ord
                    dict_ord += 1
                if dai.value not in self.dict_value:
                    self.dict_value[dai.value] = dict_ord
                    dict_ord += 1

        return dict_ord

    def get_embeddings(self, da):
        """Get the embeddings (index IDs) for a dialogue act."""
        # DA embeddings (slot - value; size == 2x self.max_da_len)
        da_emb_idxs = []
        for dai in da[:self.max_da_len]:
            da_emb_idxs.append([self.dict_slot.get(dai.name, self.UNK_SLOT),
                                self.dict_value.get(dai.value, self.UNK_VALUE)])
        # pad with "unknown"
        for _ in xrange(len(da_emb_idxs), self.max_da_len):
            da_emb_idxs.append([self.UNK_SLOT, self.UNK_VALUE])

        return da_emb_idxs

    def get_embeddings_shape(self):
        return [self.max_da_len, 2]


class TreeEmbeddingExtract(EmbeddingExtract):
    """Extracting embeddings for trees (either parent_lemma-formeme-child_lemma, or
    with the addition of previous_lemma)."""

    UNK_T_LEMMA = 2
    UNK_FORMEME = 3

    def __init__(self, cfg):
        super(TreeEmbeddingExtract, self).__init__()

        self.dict_t_lemma = {'UNK_T_LEMMA': self.UNK_T_LEMMA}
        self.dict_formeme = {'UNK_FORMEME': self.UNK_FORMEME}
        self.max_tree_len = cfg.get('max_tree_len', 20)
        # 'emb_prev' = embeddings incl. prev node at each step
        self.prev_node_emb = cfg.get('nn', 'emb') == 'emb_prev'

    def init_dict(self, train_trees, dict_ord=None):
        """Initialize dictionary, given training trees (store t-lemmas and formemes,
        assign them IDs).

        @param train_das: training DAs
        @param dict_ord: lowest ID to be assigned (if None, it is initialized to MIN_VALID)
        @return: the highest ID assigned + 1 (the current lowest available ID)
        """
        if dict_ord is None:
            dict_ord = self.MIN_VALID

        for tree in train_trees:
            for t_lemma, formeme in tree.nodes:
                if t_lemma not in self.dict_t_lemma:
                    self.dict_t_lemma[t_lemma] = dict_ord
                    dict_ord += 1
                if formeme not in self.dict_formeme:
                    self.dict_formeme[formeme] = dict_ord
                    dict_ord += 1

        return dict_ord

    def get_embeddings(self, tree):
        """Get the embeddings (index IDs) for a tree."""

        # parent_lemma - formeme - lemma, + adding previous_lemma for emb_prev
        tree_emb_idxs = []
        for pos in xrange(1, min(self.max_tree_len + 1, len(tree))):
            t_lemma, formeme = tree.nodes[pos]
            parent_ord = tree.parents[pos]
            node_emb_idxs = [self.dict_t_lemma.get(tree.nodes[parent_ord].t_lemma, self.UNK_T_LEMMA),
                             self.dict_formeme.get(formeme, self.UNK_FORMEME),
                             self.dict_t_lemma.get(t_lemma, self.UNK_T_LEMMA)]
            if self.prev_node_emb:
                node_emb_idxs.append(self.dict_t_lemma.get(tree.nodes[pos - 1].t_lemma,
                                                           self.UNK_T_LEMMA))
            tree_emb_idxs.append(node_emb_idxs)

        # pad with unknown values (except for last lemma in case of emb_prev)
        for pos in xrange(len(tree) - 1, self.max_tree_len):
            node_emb_idxs = [self.UNK_T_LEMMA, self.UNK_FORMEME, self.UNK_T_LEMMA]
            if self.prev_node_emb:
                node_emb_idxs.append(self.dict_t_lemma.get(tree.nodes[-1].t_lemma, self.UNK_T_LEMMA)
                                     if pos == len(tree) - 1
                                     else self.UNK_T_LEMMA)
            tree_emb_idxs.append(node_emb_idxs)

        return tree_emb_idxs

    def get_embeddings_shape(self):
        return [self.max_tree_len, 4 if self.prev_node_emb else 3]


class DAEmbeddingSeq2SeqExtract(EmbeddingExtract):

    UNK_SLOT = 0
    UNK_VALUE = 1
    UNK_ACT = 2

    def __init__(self, cfg={}):
        super(DAEmbeddingSeq2SeqExtract, self).__init__()

        self.dict_act = {'UNK_ACT': self.UNK_ACT}
        self.dict_slot = {'UNK_SLOT': self.UNK_SLOT}
        self.dict_value = {'UNK_VALUE': self.UNK_VALUE}
        self.max_da_len = cfg.get('max_da_len', 10)
        self.sort = cfg.get('sort_da_emb', False)

    def init_dict(self, train_das, dict_ord=None):
        """"""
        if dict_ord is None:
            dict_ord = self.MIN_VALID

        for da in train_das:
            for dai in da:
                if dai.dat not in self.dict_act:
                    self.dict_act[dai.dat] = dict_ord
                    dict_ord += 1
                if dai.name not in self.dict_slot:
                    self.dict_slot[dai.name] = dict_ord
                    dict_ord += 1
                if dai.value not in self.dict_value:
                    self.dict_value[dai.value] = dict_ord
                    dict_ord += 1

        return dict_ord

    def get_embeddings(self, da):
        """"""
        # list the IDs of act types, slots, values
        da_emb_idxs = []
        sorted_da = da
        if hasattr(self, 'sort') and self.sort:
            sorted_da = sorted(da, cmp=lambda a, b:
                               cmp(a.dat, b.dat) or cmp(a.name, b.name) or cmp(a.value, b.value))
        for dai in sorted_da[:self.max_da_len]:
            da_emb_idxs.append(self.dict_act.get(dai.dat, self.UNK_ACT))
            da_emb_idxs.append(self.dict_slot.get(dai.name, self.UNK_SLOT))
            da_emb_idxs.append(self.dict_value.get(dai.value, self.UNK_VALUE))
        # left-pad with unknown
        padding = []
        if len(da) < self.max_da_len:
            padding = [self.UNK_ACT, self.UNK_SLOT, self.UNK_VALUE] * (self.max_da_len - len(da))
        return padding + da_emb_idxs

    def get_embeddings_shape(self):
        """Return the shape of the embedding matrix (for one object, disregarding batches)."""
        return [3 * self.max_da_len]


class TreeEmbeddingSeq2SeqExtract(EmbeddingExtract):
    # TODO try relative parents (good for non-projective, may be bad for non-local) ???

    UNK_T_LEMMA = 0
    UNK_FORMEME = 1
    BR_OPEN = 2
    BR_CLOSE = 3
    GO = 4
    STOP = 5
    VOID = 6
    MIN_VALID = 7

    def __init__(self, cfg={}):
        super(TreeEmbeddingSeq2SeqExtract, self).__init__()

        self.dict_t_lemma = {'UNK_T_LEMMA': self.UNK_T_LEMMA}
        self.dict_formeme = {'UNK_FORMEME': self.UNK_FORMEME}
        self.max_tree_len = cfg.get('max_tree_len', 25)
        self.id_to_string = {self.UNK_T_LEMMA: '<UNK_T_LEMMA>',
                             self.UNK_FORMEME: '<UNK_FORMEME>',
                             self.BR_OPEN: '<(>',
                             self.BR_CLOSE: '<)>',
                             self.GO: '<GO>',
                             self.STOP: '<STOP>',
                             self.VOID: '<>'}

    def init_dict(self, train_trees, dict_ord=None):
        """"""
        if dict_ord is None:
            dict_ord = self.MIN_VALID

        for tree in train_trees:
            for t_lemma, formeme in tree.nodes:
                if t_lemma not in self.dict_t_lemma:
                    self.dict_t_lemma[t_lemma] = dict_ord
                    self.id_to_string[dict_ord] = t_lemma
                    dict_ord += 1
                if formeme not in self.dict_formeme:
                    self.dict_formeme[formeme] = dict_ord
                    self.id_to_string[dict_ord] = formeme
                    dict_ord += 1

        return dict_ord

    def _get_subtree_embeddings(self, tree, root_idx):
        """Bracketed-style embeddings for a projective tree."""
        embs = [self.BR_OPEN]

        for left_child_idx in tree.children_idxs(root_idx, left_only=True):
            embs.extend(self._get_subtree_embeddings(tree, left_child_idx))

        embs.extend([self.dict_t_lemma.get(tree[root_idx].t_lemma, self.UNK_T_LEMMA),
                     self.dict_formeme.get(tree[root_idx].formeme, self.UNK_FORMEME)])

        for right_child_idx in tree.children_idxs(root_idx, right_only=True):
            embs.extend(self._get_subtree_embeddings(tree, right_child_idx))

        embs.append(self.BR_CLOSE)
        return embs

    def get_embeddings(self, tree):
        """Return (list of) embedding (integer) IDs for a tree."""

        # get tree embeddings recursively
        tree_emb_idxs = [self.GO] + self._get_subtree_embeddings(tree, 0) + [self.STOP]

        # right-pad with unknown
        shape = self.get_embeddings_shape()[0]
        padding = [self.VOID] * (shape - len(tree_emb_idxs))

        return tree_emb_idxs + padding

    def ids_to_strings(self, emb):
        """Given embedding IDs, return list of strings where all VOIDs at the end are truncated."""

        # skip VOIDs at the end
        i = len(emb) - 1
        while i > 0 and emb[i] == self.VOID:
            i -= 1

        # convert all IDs to their tokens
        ret = [unicode(self.id_to_string.get(tok_id, '<???>')) for tok_id in emb[:i + 1]]
        return ret

    def ids_to_tree(self, emb):
        """Rebuild a tree from the embeddings (token IDs).

        @param emb: source embeddings (token IDs)
        @return: the corresponding tree
        """

        tree = TreeData()
        tree.nodes = []  # override the technical root -- the tree will be created including the technical root
        tree.parents = []

        # build the tree recursively (start at position 2 to skip the <GO> symbol and 1st opening bracket)
        self._create_subtree(tree, -1, emb, 2)
        return tree

    def _create_subtree(self, tree, parent_idx, emb, pos):
        """Recursive subroutine used for `ids_to_tree()`, do not use otherwise.
        Solves a subtree (starting just after the opening bracket, returning a position
        just after the corresponding closing bracket).

        @param tree: the tree to work on (will be enhanced by the subtree)
        @param parent_idx: the ID of the parent for the current subtree
        @param emb: the source embeddings
        @param pos: starting position in the source embeddings
        @return: the final position used in the current subtree
        """

        if pos >= len(emb):  # avoid running out of the tree (for invalid trees)
            return pos

        node_idx = tree.create_child(parent_idx, len(tree), NodeData(None, None))
        t_lemma = None
        formeme = None

        while pos < len(emb) and emb[pos] not in [self.BR_CLOSE, self.STOP, self.VOID]:

            if emb[pos] == self.BR_OPEN:
                # recurse into subtree
                pos = self._create_subtree(tree, node_idx, emb, pos + 1)

            elif emb[pos] == self.UNK_T_LEMMA:
                if t_lemma is None:
                    t_lemma = self.id_to_string[self.UNK_T_LEMMA]
                pos += 1

            elif emb[pos] == self.UNK_FORMEME:
                if formeme is None:
                    formeme = self.id_to_string[self.UNK_FORMEME]
                pos += 1

            elif emb[pos] >= self.MIN_VALID:
                # remember the t-lemma and formeme for normal nodes
                token = self.id_to_string.get(emb[pos])
                if t_lemma is None:
                    t_lemma = token
                elif formeme is None:
                    formeme = token

                # move the node to its correct position
                # (which we now know it's at the current end of the tree)
                if node_idx != len(tree) - 1:
                    tree.move_node(node_idx, len(tree) - 1)
                    node_idx = len(tree) - 1
                pos += 1

        if pos < len(emb) and emb[pos] == self.BR_CLOSE:
            # skip this closing bracket so that we don't process it next time
            pos += 1

        # fill in the t-lemma and formeme that we've found
        if t_lemma is not None or formeme is not None:
            tree.nodes[node_idx] = NodeData(t_lemma, formeme)

        return pos

    def get_embeddings_shape(self):
        """Return the shape of the embedding matrix (for one object, disregarding batches)."""
        return [4 * self.max_tree_len + 2]


class TokenEmbeddingSeq2SeqExtract(EmbeddingExtract):
    """Extracting token emeddings from a string (array of words)."""

    VOID = 0
    GO = 1
    STOP = 2
    UNK = 3
    PLURAL_S = 4
    MIN_VALID = 5

    def __init__(self, cfg={}):
        self.max_sent_len = cfg.get('max_sent_len', 50)
        self.dict = {'UNK': self.UNK}
        self.rev_dict = {self.VOID: '<VOID>', self.GO: '<GO>',
                         self.STOP: '<STOP>', self.UNK: '<UNK>',
                         self.PLURAL_S: '<-s>'}

    def init_dict(self, train_sents, dict_ord=None):
        """Initialize embedding dictionary (word -> id)."""
        if dict_ord is None:
            dict_ord = self.MIN_VALID

        for sent in train_sents:
            for form, tag in sent:
                if tag == 'NNS' and form.endswith('s'):
                    form = form[:-1]  # TODO this is very stupid, but probably works with BAGEL
                if form not in self.dict:
                    self.dict[form] = dict_ord
                    self.rev_dict[dict_ord] = form
                    dict_ord += 1

        return dict_ord

    def get_embeddings(self, sent):
        """Get the embeddings of a sentence (list of word form/tag pairs)."""
        embs = [self.GO]
        for form, tag in sent:
            add_plural = False
            if tag == 'NNS' and form.endswith('s'):
                add_plural = True
                form = form[-1]
            embs.append(self.dict.get(form, self.UNK))
            if add_plural:
                embs.append(self.PLURAL_S)

        embs += [self.STOP]
        if len(embs) > self.max_sent_len + 2:
            embs = embs[:self.max_sent_len + 2]
        elif len(embs) < self.max_sent_len + 2:
            embs += [self.VOID] * (self.max_sent_len + 2 - len(embs))

        return embs

    def get_embeddings_shape(self):
        """Return the shape of the embedding matrix (for one object, disregarding batches)."""
        return [self.max_sent_len + 2]

    def ids_to_strings(self, emb):
        """Given embedding IDs, return list of strings where all VOIDs at the end are truncated."""

        # skip VOIDs at the end
        i = len(emb) - 1
        while i > 0 and emb[i] == self.VOID:
            i -= 1

        # convert all IDs to their tokens
        ret = [unicode(self.rev_dict.get(tok_id, '<???>')) for tok_id in emb[:i + 1]]

        return ret

    def ids_to_tree(self, emb):
        """Create a fake (flat) t-tree from token embeddings (IDs).

        @param emb: source embeddings (token IDs)
        @return: the corresponding tree
        """

        tree = TreeData()
        tokens = self.ids_to_strings(emb)

        for token in tokens:
            if token in ['<GO>', '<STOP>', '<VOID>']:
                continue
            if token == '<-s>' and tree.nodes[-1].t_lemma is not None:
                tree.nodes[-1] = NodeData(tree.nodes[-1].t_lemma + 's', 'x')
            elif token == '<-s>':
                continue
            else:
                tree.create_child(0, len(tree), NodeData(token, 'x'))

        return tree
