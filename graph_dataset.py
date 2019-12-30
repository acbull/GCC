#!/usr/bin/env python
# encoding: utf-8
# File Name: graph_dataset.py
# Author: Jiezhong Qiu
# Create Time: 2019/12/11 12:17
# TODO:

import numpy as np
import dgl
import networkx as nx
import matplotlib.pyplot as plt
import torch
from dgl.data import AmazonCoBuy, Coauthor
import dgl.data

from cogdl.datasets import build_dataset
import data_util

class GraphDataset(torch.utils.data.Dataset):
    def __init__(self, rw_hops=64, subgraph_size=64, restart_prob=0.8, hidden_size=32, step_dist=[1.0, 0.0, 0.0]):
        self.rw_hops = rw_hops
        self.subgraph_size = subgraph_size
        self.restart_prob = restart_prob
        self.hidden_size = hidden_size
        self.step_dist = step_dist
        assert sum(step_dist) == 1.0
        assert(hidden_size > 1)
        #  graphs = []
        graphs, _ = dgl.data.utils.load_graphs("data_bin/dgl/lscc_graphs.bin", [0, 1, 2])
        for name in ["cs", "physics"]:
            g = Coauthor(name)[0]
            g.remove_nodes((g.in_degrees() == 0).nonzero().squeeze())
            g.readonly()
            graphs.append(g)
        for name in ["computers", "photo"]:
            g = AmazonCoBuy(name)[0]
            g.remove_nodes((g.in_degrees() == 0).nonzero().squeeze())
            g.readonly()
            graphs.append(g)
        # more graphs are comming ...
        print("load graph done")
        self.graphs = graphs
        self.length = sum([g.number_of_nodes() for g in self.graphs])

    def __len__(self):
        return self.length

    def getplot(self, idx):
        graph_q, graph_k = self.__getitem__(idx)
        graph_q = graph_q.to_networkx()
        graph_k = graph_k.to_networkx()
        figure_q = plt.figure(figsize=(10, 10))
        nx.draw(graph_q)
        plt.draw()
        image_q = data_util.plot_to_image(figure_q)
        figure_k = plt.figure(figsize=(10, 10))
        nx.draw(graph_k)
        plt.draw()
        image_k = data_util.plot_to_image(figure_k)
        return image_q, image_k


    def __getitem__(self, idx):
        graph_idx = 0
        node_idx = idx
        for i in range(len(self.graphs)):
            if  node_idx < self.graphs[i].number_of_nodes():
                graph_idx = i
                break
            else:
                node_idx -= self.graphs[i].number_of_nodes()

        step = np.random.choice(len(self.step_dist), 1, p=self.step_dist)[0]
        if step == 0:
            other_node_idx = node_idx
        else:
            other_node_idx = dgl.contrib.sampling.random_walk(
                    g=self.graphs[graph_idx],
                    seeds=[node_idx],
                    num_traces=1,
                    num_hops=step
                    )[0][0][-1].item()

        traces = dgl.contrib.sampling.random_walk_with_restart(
            self.graphs[graph_idx],
            seeds=[node_idx, other_node_idx],
            restart_prob=self.restart_prob,
            max_nodes_per_seed=self.rw_hops)

        graph_q = data_util._rwr_trace_to_dgl_graph(
                g=self.graphs[graph_idx],
                seed=node_idx,
                trace=traces[0],
                hidden_size=self.hidden_size)
        graph_k = data_util._rwr_trace_to_dgl_graph(
                g=self.graphs[graph_idx],
                seed=other_node_idx,
                trace=traces[1],
                hidden_size=self.hidden_size)
        return graph_q, graph_k


class CogDLGraphDataset(GraphDataset):
    def __init__(self, dataset, rw_hops=64, subgraph_size=64, restart_prob=0.8, hidden_size=32, step_dist=[1.0, 0.0, 0.0]):
        self.rw_hops = rw_hops
        self.subgraph_size = subgraph_size
        self.restart_prob = restart_prob
        self.hidden_size = hidden_size
        self.step_dist = step_dist
        assert(hidden_size > 1)

        class tmp():
            # HACK
            pass
        args = tmp()
        args.dataset = dataset
        data = build_dataset(args)[0]
        self.graph = dgl.DGLGraph()
        src, dst = data.edge_index.tolist()
        self.graph.add_nodes(data.y.shape[0])
        self.graph.add_edges(src, dst)
        # self.graph = dgl.transform.remove_self_loop(self.graph)
        self.graph.remove_nodes((self.graph.out_degrees() == 0).nonzero().squeeze())
        self.graph.readonly()
        self.graphs = [self.graph]
        self.length = sum([g.number_of_nodes() for g in self.graphs])

if __name__ == '__main__':
    # graph_dataset = GraphDataset()
    graph_dataset = CogDLGraphDataset(dataset="wikipedia")
    pq, pk = graph_dataset.getplot(0)
    graph_loader = torch.utils.data.DataLoader(
            dataset=graph_dataset,
            batch_size=20,
            collate_fn=data_util.batcher(),
            shuffle=True,
            num_workers=4)
    for step, batch in enumerate(graph_loader):
        print(batch.graph_q)
        print(batch.graph_q.ndata['x'].shape)
        print(batch.graph_q.batch_size)
        print("max", batch.graph_q.edata['efeat'].max())
        break
