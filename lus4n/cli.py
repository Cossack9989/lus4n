import os
import uuid
import argparse
import tempfile

import networkx as nx
import matplotlib.pyplot as plt

from joblib import dump, load

from lus4n.graph import scan_path


parser = argparse.ArgumentParser(description="Lus4n: lua call graph generation")
parser.add_argument('-p', '--path', type=str)
parser.add_argument('-s', '--storage', type=str)
parser.add_argument('-q', '--query', type=str)
args = parser.parse_args()
if args.path:
    assert os.path.exists(args.path)
    if args.storage:
        assert os.path.exists(os.path.dirname(args.storage))
        storage = args.storage
    else:
        temp_dir = tempfile.gettempdir()
        storage = os.path.join(temp_dir, str(uuid.uuid4())) + '.jb'
elif args.query:
    assert args.storage and os.path.exists(args.storage)
    storage = args.storage
else:
    temp_dir = tempfile.gettempdir()
    storage = os.path.join(temp_dir, str(uuid.uuid4())) + '.jb'


def main():

    if args.path:
        d, g = scan_path(args.path, None, False)
        dump(g, storage)
    elif args.query:
        g: nx.DiGraph = load(args.storage)
        if args.query in g.nodes:
            nodes: set = nx.ancestors(g, args.query)
            file_node_list = []
            func_node_list = []
            for node in nodes:
                if "role" in g.nodes[node] and g.nodes[node]["role"] == "file":
                    file_node_list.append(node)
                else:
                    func_node_list.append(node)
            if args.query not in nodes:
                nodes.add(args.query)
            sg = g.subgraph(nodes)
            pos = nx.spring_layout(sg)
            nx.draw_networkx_nodes(sg, pos, nodelist=file_node_list, node_size=30, node_color='blue')
            nx.draw_networkx_nodes(sg, pos, nodelist=func_node_list, node_size=15, node_color='green')
            nx.draw_networkx_nodes(sg, pos, nodelist=[args.query], node_size=50, node_color='red')
            nx.draw_networkx_edges(sg, pos)
            nx.draw_networkx_labels(sg, pos, font_size=5)
            # nx.draw_circular(sg, with_labels=True, font_size=8)
            plt.show()
        else:
            print(f"no such node {args.query}")


if __name__ == "__main__":
    main()
