import logging
import random
import torch
from tqdm import tqdm
import numpy as np
from tree_sitter import Language
from tree_sitter import Parser

logger = logging.getLogger(__name__)
from torch.utils.data import Dataset, TensorDataset
import json
from dataset.parser import DFG_python,DFG_java,DFG_ruby,DFG_go,DFG_php,DFG_javascript

from dataset.parser import (remove_comments_and_docstrings,
                          tree_to_token_index,
                          index_to_code_token)

dfg_function={
    # 'python':DFG_python,
    'java':DFG_java,
    # 'ruby':DFG_ruby,
    # 'go':DFG_go,
    # 'php':DFG_php,
    # 'javascript':DFG_javascript
}

# load parsers
parsers={}
for lang in dfg_function:
    LANGUAGE = Language('dataset/parser/my-languages.so', lang)
    parser = Parser()
    parser.set_language(LANGUAGE)
    parser = [parser,dfg_function[lang]]
    parsers[lang]= parser


class UnixInputFeatures(object):
    """A single training/test features for a example."""
    def __init__(self,
                 input_tokens,
                 input_ids,
                 label,
                 url1,
                 url2

    ):
        self.input_tokens = input_tokens
        self.input_ids = input_ids
        self.label=label
        self.url1=url1
        self.url2=url2


class CloneInputFeatures(object):
    """A single training/test features for a example."""

    def __init__(self,
                 example_id,
                 source_ids,
                 label,
                 url1,
                 url2
                 ):
        self.example_id = example_id
        self.source_ids = source_ids
        self.label = label
        self.url1 = url1
        self.url2 = url2


class InputFeatures(object):
    """A single training/test features for a example."""

    def __init__(self,
                 input_tokens_1,
                 input_ids_1,
                 position_idx_1,
                 dfg_to_code_1,
                 dfg_to_dfg_1,
                 input_tokens_2,
                 input_ids_2,
                 position_idx_2,
                 dfg_to_code_2,
                 dfg_to_dfg_2,
                 label,
                 url1,
                 url2

                 ):
        # The first code function
        self.input_tokens_1 = input_tokens_1
        self.input_ids_1 = input_ids_1
        self.position_idx_1 = position_idx_1
        self.dfg_to_code_1 = dfg_to_code_1
        self.dfg_to_dfg_1 = dfg_to_dfg_1

        # The second code function
        self.input_tokens_2 = input_tokens_2
        self.input_ids_2 = input_ids_2
        self.position_idx_2 = position_idx_2
        self.dfg_to_code_2 = dfg_to_code_2
        self.dfg_to_dfg_2 = dfg_to_dfg_2

        # label
        self.label = label
        self.url1 = url1
        self.url2 = url2


def extract_dataflow(code, parser,lang):
    #remove comments
    try:
        code=remove_comments_and_docstrings(code,lang)
    except:
        pass
    #obtain dataflow
    if lang=="php":
        code="<?php"+code+"?>"
    try:
        tree = parser[0].parse(bytes(code,'utf8'))
        root_node = tree.root_node
        tokens_index=tree_to_token_index(root_node)
        code=code.split('\n')
        code_tokens=[index_to_code_token(x,code) for x in tokens_index]
        index_to_code={}
        for idx,(index,code) in enumerate(zip(tokens_index,code_tokens)):
            index_to_code[index]=(idx,code)
        try:
            DFG,_=parser[1](root_node,index_to_code,{})
        except:
            DFG=[]
        DFG=sorted(DFG,key=lambda x:x[1])
        indexs=set()
        for d in DFG:
            if len(d[-1])!=0:
                indexs.add(d[1])
            for x in d[-1]:
                indexs.add(x)
        new_DFG=[]
        for d in DFG:
            if d[1] in indexs:
                new_DFG.append(d)
        dfg=new_DFG
    except Exception as e:
        print(e)
        dfg=[]
    return code_tokens,dfg


def convert_clone_examples_to_features(idx, item):
    # example, example_index, tokenizer, args = item
    url1, url2, label, tokenizer, args, cache, url_to_code = item
    source = url_to_code[url1]
    target = url_to_code[url2]

    source_str = "{}: {}".format(args.task, source)
    target_str = "{}: {}".format(args.task, target)

    # if args.model_type in ['t5', 'codet5'] and args.add_task_prefix:
    #     source_str = "{}: {}".format(args.task, source)
    #     target_str = "{}: {}".format(args.task, target)
    # else:
    #     source_str = source
    #     target_str = target
    code1 = tokenizer.encode(source_str, max_length=args.max_source_length, padding='max_length', truncation=True)
    code2 = tokenizer.encode(target_str, max_length=args.max_source_length, padding='max_length', truncation=True)
    source_ids = code1 + code2
    return CloneInputFeatures(idx, source_ids, label, url1, url2)

def convert_examples_to_features(item):
    # source
    url1, url2, label, tokenizer, args, cache, url_to_code = item
    parser = parsers['java']

    for url in [url1, url2]:
        if url not in cache:
            func = url_to_code[url]

            # extract data flow
            code_tokens, dfg = extract_dataflow(func, parser, 'java')
            code_tokens = [tokenizer.tokenize('@ ' + x)[1:] if idx != 0 else tokenizer.tokenize(x) for idx, x in
                           enumerate(code_tokens)]
            ori2cur_pos = {}
            ori2cur_pos[-1] = (0, 0)
            for i in range(len(code_tokens)):
                ori2cur_pos[i] = (ori2cur_pos[i - 1][1], ori2cur_pos[i - 1][1] + len(code_tokens[i]))
            code_tokens = [y for x in code_tokens for y in x]

            # truncating
            code_tokens = code_tokens[
                          :args.code_length + args.data_flow_length - 3 - min(len(dfg), args.data_flow_length)][
                          :512 - 3]
            source_tokens = [tokenizer.cls_token] + code_tokens + [tokenizer.sep_token]
            source_ids = tokenizer.convert_tokens_to_ids(source_tokens)
            position_idx = [i + tokenizer.pad_token_id + 1 for i in range(len(source_tokens))]
            dfg = dfg[:args.code_length + args.data_flow_length - len(source_tokens)]
            source_tokens += [x[0] for x in dfg]
            position_idx += [0 for x in dfg]
            source_ids += [tokenizer.unk_token_id for x in dfg]
            padding_length = args.code_length + args.data_flow_length - len(source_ids)
            position_idx += [tokenizer.pad_token_id] * padding_length
            source_ids += [tokenizer.pad_token_id] * padding_length

            # reindex
            reverse_index = {}
            for idx, x in enumerate(dfg):
                reverse_index[x[1]] = idx
            for idx, x in enumerate(dfg):
                dfg[idx] = x[:-1] + ([reverse_index[i] for i in x[-1] if i in reverse_index],)
            dfg_to_dfg = [x[-1] for x in dfg]
            dfg_to_code = [ori2cur_pos[x[1]] for x in dfg]
            length = len([tokenizer.cls_token])
            dfg_to_code = [(x[0] + length, x[1] + length) for x in dfg_to_code]
            cache[url] = source_tokens, source_ids, position_idx, dfg_to_code, dfg_to_dfg

    source_tokens_1, source_ids_1, position_idx_1, dfg_to_code_1, dfg_to_dfg_1 = cache[url1]
    source_tokens_2, source_ids_2, position_idx_2, dfg_to_code_2, dfg_to_dfg_2 = cache[url2]
    return InputFeatures(source_tokens_1, source_ids_1, position_idx_1, dfg_to_code_1, dfg_to_dfg_1,
                         source_tokens_2, source_ids_2, position_idx_2, dfg_to_code_2, dfg_to_dfg_2,
                         label, url1, url2)


def convert_examples_to_unix_features(code1_tokens, code2_tokens, label, url1, url2, tokenizer, args, cache):
    """convert examples to token ids"""
    code1_tokens = code1_tokens[:args.block_size - 4]
    code1_tokens = [tokenizer.cls_token, "<encoder-only>", tokenizer.sep_token] + code1_tokens + [tokenizer.sep_token]
    code2_tokens = code2_tokens[:args.block_size - 4]
    code2_tokens = [tokenizer.cls_token, "<encoder-only>", tokenizer.sep_token] + code2_tokens + [tokenizer.sep_token]

    code1_ids = tokenizer.convert_tokens_to_ids(code1_tokens)
    padding_length = args.block_size - len(code1_ids)
    code1_ids += [tokenizer.pad_token_id] * padding_length

    code2_ids = tokenizer.convert_tokens_to_ids(code2_tokens)
    padding_length = args.block_size - len(code2_ids)
    code2_ids += [tokenizer.pad_token_id] * padding_length

    source_tokens = code1_tokens + code2_tokens
    source_ids = code1_ids + code2_ids
    return UnixInputFeatures(source_tokens, source_ids, label, url1, url2)


class TextDataset(Dataset):
    def __init__(self, tokenizer, args, file_path='train'):
        self.examples = []
        self.args = args
        index_filename = file_path

        # load index
        logger.info("Creating features from index file at %s ", index_filename)
        url_to_code = {}
        with open('/'.join(index_filename.split('/')[:-1]) + '/data.jsonl') as f:
            for line in f:
                line = line.strip()
                js = json.loads(line)
                url_to_code[js['idx']] = js['func']

        # load code function according to index
        data = []
        cache = {}
        f = open(index_filename)
        with open(index_filename) as f:
            for line in f:
                line = line.strip()
                url1, url2, label = line.split('\t')
                if url1 not in url_to_code or url2 not in url_to_code:
                    continue
                if label == '0':
                    label = 0
                else:
                    label = 1
                data.append((url1, url2, label, tokenizer, args, cache, url_to_code))

        # only use 10% valid data to keep best model
        if 'valid' in file_path:
            data = random.sample(data, int(len(data) * 0.1))

        # convert example to input features
        self.examples = [convert_examples_to_features(x) for x in tqdm(data, total=len(data))]

        if 'train' in file_path:
            for idx, example in enumerate(self.examples[:3]):
                logger.info("*** Example ***")
                logger.info("idx: {}".format(idx))
                logger.info("label: {}".format(example.label))
                logger.info("input_tokens_1: {}".format([x.replace('\u0120', '_') for x in example.input_tokens_1]))
                logger.info("input_ids_1: {}".format(' '.join(map(str, example.input_ids_1))))
                logger.info("position_idx_1: {}".format(example.position_idx_1))
                logger.info("dfg_to_code_1: {}".format(' '.join(map(str, example.dfg_to_code_1))))
                logger.info("dfg_to_dfg_1: {}".format(' '.join(map(str, example.dfg_to_dfg_1))))

                logger.info("input_tokens_2: {}".format([x.replace('\u0120', '_') for x in example.input_tokens_2]))
                logger.info("input_ids_2: {}".format(' '.join(map(str, example.input_ids_2))))
                logger.info("position_idx_2: {}".format(example.position_idx_2))
                logger.info("dfg_to_code_2: {}".format(' '.join(map(str, example.dfg_to_code_2))))
                logger.info("dfg_to_dfg_2: {}".format(' '.join(map(str, example.dfg_to_dfg_2))))

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, item):
        # calculate graph-guided masked function
        attn_mask_1 = np.zeros((self.args.code_length + self.args.data_flow_length,
                                self.args.code_length + self.args.data_flow_length), dtype=bool)
        # calculate begin index of node and max length of input
        node_index = sum([i > 1 for i in self.examples[item].position_idx_1])
        max_length = sum([i != 1 for i in self.examples[item].position_idx_1])
        # sequence can attend to sequence
        attn_mask_1[:node_index, :node_index] = True
        # special tokens attend to all tokens
        for idx, i in enumerate(self.examples[item].input_ids_1):
            if i in [0, 2]:
                attn_mask_1[idx, :max_length] = True
        # nodes attend to code tokens that are identified from
        for idx, (a, b) in enumerate(self.examples[item].dfg_to_code_1):
            if a < node_index and b < node_index:
                attn_mask_1[idx + node_index, a:b] = True
                attn_mask_1[a:b, idx + node_index] = True
        # nodes attend to adjacent nodes
        for idx, nodes in enumerate(self.examples[item].dfg_to_dfg_1):
            for a in nodes:
                if a + node_index < len(self.examples[item].position_idx_1):
                    attn_mask_1[idx + node_index, a + node_index] = True

                    # calculate graph-guided masked function
        attn_mask_2 = np.zeros((self.args.code_length + self.args.data_flow_length,
                                self.args.code_length + self.args.data_flow_length), dtype=bool)
        # calculate begin index of node and max length of input
        node_index = sum([i > 1 for i in self.examples[item].position_idx_2])
        max_length = sum([i != 1 for i in self.examples[item].position_idx_2])
        # sequence can attend to sequence
        attn_mask_2[:node_index, :node_index] = True
        # special tokens attend to all tokens
        for idx, i in enumerate(self.examples[item].input_ids_2):
            if i in [0, 2]:
                attn_mask_2[idx, :max_length] = True
        # nodes attend to code tokens that are identified from
        for idx, (a, b) in enumerate(self.examples[item].dfg_to_code_2):
            if a < node_index and b < node_index:
                attn_mask_2[idx + node_index, a:b] = True
                attn_mask_2[a:b, idx + node_index] = True
        # nodes attend to adjacent nodes
        for idx, nodes in enumerate(self.examples[item].dfg_to_dfg_2):
            for a in nodes:
                if a + node_index < len(self.examples[item].position_idx_2):
                    attn_mask_2[idx + node_index, a + node_index] = True

        return (torch.tensor(self.examples[item].input_ids_1),
                torch.tensor(self.examples[item].position_idx_1),
                torch.tensor(attn_mask_1),
                torch.tensor(self.examples[item].input_ids_2),
                torch.tensor(self.examples[item].position_idx_2),
                torch.tensor(attn_mask_2),
                torch.tensor(self.examples[item].label))


class T5TextDataset(Dataset):
    def __init__(self, tokenizer, args, file_path='train'):
        self.examples = []
        self.args = args
        index_filename = file_path

        # load index
        logger.info("Creating features from index file at %s ", index_filename)
        url_to_code = {}
        with open('/'.join(index_filename.split('/')[:-1]) + '/data.jsonl') as f:
            for line in f:
                line = line.strip()
                js = json.loads(line)
                url_to_code[js['idx']] = js['func']

        # load code function according to index
        data = []
        cache = {}
        f = open(index_filename)
        with open(index_filename) as f:
            for line in f:
                line = line.strip()
                url1, url2, label = line.split('\t')
                if url1 not in url_to_code or url2 not in url_to_code:
                    continue
                if label == '0':
                    label = 0
                else:
                    label = 1
                data.append((url1, url2, label, tokenizer, args, cache, url_to_code))

        # only use 10% valid data to keep best model
        if 'valid' in file_path:
            data = random.sample(data, int(len(data) * 0.1))

        # convert example to input features

        self.examples = [convert_clone_examples_to_features(idx, x) for idx, x in tqdm(enumerate(data), total=len(data))]

        # if 'train' in file_path:
        #     for idx, example in enumerate(self.examples[:3]):
        #         logger.info("*** Example ***")
        #         logger.info("idx: {}".format(idx))
        #         logger.info("label: {}".format(example.label))
        #         logger.info("input_tokens_1: {}".format([x.replace('\u0120', '_') for x in example.input_tokens_1]))
        #         logger.info("input_ids_1: {}".format(' '.join(map(str, example.input_ids_1))))
        #         logger.info("position_idx_1: {}".format(example.position_idx_1))
        #         logger.info("dfg_to_code_1: {}".format(' '.join(map(str, example.dfg_to_code_1))))
        #         logger.info("dfg_to_dfg_1: {}".format(' '.join(map(str, example.dfg_to_dfg_1))))
        #
        #         logger.info("input_tokens_2: {}".format([x.replace('\u0120', '_') for x in example.input_tokens_2]))
        #         logger.info("input_ids_2: {}".format(' '.join(map(str, example.input_ids_2))))
        #         logger.info("position_idx_2: {}".format(example.position_idx_2))
        #         logger.info("dfg_to_code_2: {}".format(' '.join(map(str, example.dfg_to_code_2))))
        #         logger.info("dfg_to_dfg_2: {}".format(' '.join(map(str, example.dfg_to_dfg_2))))

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, item):

        return (torch.tensor(self.examples[item].source_ids),
                torch.tensor(self.examples[item].label)
                )


def get_example(item):
    url1, url2, label, tokenizer, args, cache, url_to_code = item
    if url1 in cache:
        code1 = cache[url1].copy()
    else:
        try:
            code = ' '.join(url_to_code[url1].split())
        except:
            code = ""
        code1 = tokenizer.tokenize(code)
    if url2 in cache:
        code2 = cache[url2].copy()
    else:
        try:
            code = ' '.join(url_to_code[url2].split())
        except:
            code = ""
        code2 = tokenizer.tokenize(code)

    return convert_examples_to_unix_features(code1, code2, label, url1, url2, tokenizer, args, cache)


class UnixTextDataset(Dataset):
    def __init__(self, tokenizer, args, file_path, pool=None):
        postfix = file_path.split('/')[-1].split('.txt')[0]
        self.examples = []
        index_filename = file_path
        logger.info("Creating features from index file at %s ", index_filename)
        url_to_code = {}
        with open('/'.join(index_filename.split('/')[:-1])+'/data.jsonl') as f:
            for line in f:
                line = line.strip()
                js = json.loads(line)
                url_to_code[js['idx']] = js['func']

        data = []
        cache = {}
        f = open(index_filename)
        with open(index_filename) as f:
            for line in f:
                line = line.strip()
                url1,url2,label = line.split('\t')
                if url1 not in url_to_code or url2 not in url_to_code:
                    continue
                if label == '0':
                    label = 0
                else:
                    label = 1
                data.append((url1,url2,label,tokenizer, args,cache,url_to_code))
        if 'valid' in postfix:
            data = random.sample(data,int(len(data)*0.1))

        self.examples = pool.map(get_example, tqdm(data,total=len(data)))
        if 'train' in postfix:
            for idx, example in enumerate(self.examples[:3]):
                    logger.info("*** Example ***")
                    logger.info("idx: {}".format(idx))
                    logger.info("label: {}".format(example.label))
                    logger.info("input_tokens: {}".format([x.replace('\u0120','_') for x in example.input_tokens]))
                    logger.info("input_ids: {}".format(' '.join(map(str, example.input_ids))))

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, item):
        return torch.tensor(self.examples[item].input_ids),torch.tensor(self.examples[item].label)
