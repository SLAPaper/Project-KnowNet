from typing import Any, Dict, List, Text, Tuple

from .abc.graph import (EdgeKeyPair, EdgeKeyType, EdgeNamePair, EdgeValDict, GraphDataSource, GraphKeyType, GraphNameType, GraphType, GraphValType, NodeKeyPair,
                        NodeKeyType, NodeValDict)
# from .exception import NotSupportedError

try:
    import neo4j
except ImportError:
    raise ImportError('This data source requires neo4j to be installed.')


class Neo4jDS(GraphDataSource):
    DEFAULT_GRAPH_KEY = '_default'
    DEFAULT_NODE_KEY = NodeKeyPair('_default', 0)
    DEFAULT_EDGE_KEY = EdgeKeyPair('_default', EdgeNamePair(0, 1))
    DEFAULT_GRAPH_VAL = GraphValType(graph_type="DiGraph", attr={}, nodes=[], edges=[], node_attr={}, edge_attr={})

    GRAPH_FAKE_NODE_LABEL = 'Graph_fakenode'
    GRAPH_NAME_PROPERTY = 'graph_name_'
    NODE_NAME_PROPERTY = 'node_name_'

    def __init__(self, config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)

        self._uri = config.check_get(['init', 'uri'])
        self._user = config.check_get(['init', 'user'])
        self._password = config.check_get(['init', 'password'])

        self._driver = neo4j.GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def __del__(self):
        self._driver.close()

    def clear(self):
        cypher = ("MATCH (node) " "DETACH DELETE node;")
        with self._driver.session() as session:
            session.run(cypher)

    def _filter_graph(self, key: GraphKeyType) -> List[GraphNameType]:
        graph_cond: List[Tuple[Any, Any]] = []

        if isinstance(key, str):
            graph_cond.append((key, None))

        if isinstance(key, list):
            for g_n in key:
                graph_cond.append((g_n, None))

        if isinstance(key, dict):
            for g_n, c in key.items():
                graph_cond.append((g_n, c))

        result = []
        for graph_name, _ in graph_cond:
            if graph_name.startswith('@*'):
                with self._driver.session() as session:
                    graph_names = session.run("CALL db.labels() YIELD label;")

                for g_n in graph_names:
                    result.append(g_n)
                    # TODO: wildcards and filters
            else:
                result.append(graph_name)

        return result

    def create_graph(self, key: GraphKeyType, val: GraphValType) -> List[GraphNameType]:
        target = self._filter_graph(key)

        results: List = []
        for graph_name in target:
            # create Graph fake node
            # graph_type = val.graph_type
            attr = {**val.attr}
            attr[self.GRAPH_NAME_PROPERTY] = graph_name

            graph_cypher = f"CREATE (n:{self.GRAPH_FAKE_NODE_LABEL} $attr);"

            # create nodes
            nodes = val.nodes
            node_attr = val.node_attr
            new_nodes: List = []
            for node in nodes:
                tmp_node = {self.NODE_NAME_PROPERTY: node}
                tmp_node.update(node_attr)
                new_nodes.append(tmp_node)

            node_cypher = ("UNWIND $nodes AS prop " f"CREATE (n:{graph_name}) " "SET n = prop;")

            # create edges
            edges = val.edges
            edge_attr = val.edge_attr
            new_edges: List = [{'n1': edge.node1, 'n2': edge.node2, 'prop': edge_attr} for edge in edges]

            edge_cypher = ("UNWIND edges AS edge "
                           f"MATCH (n:{graph_name}), (m:{graph_name}) "
                           f"WHERE n.{self.NODE_NAME_PROPERTY} = edge.n1 AND m.{self.NODE_NAME_PROPERTY} = edge.n2"
                           f"CREATE (n)-[r:{graph_name}]->(m)"
                           "SET r = edge.prop;")

            with self._driver.session() as session:
                tx = session.begin_transaction()
                tx.run(graph_cypher, attr=attr)
                tx.run(node_cypher, nodes=new_nodes)
                tx.run(edge_cypher, edges=new_edges)
                tx.commit()

        return results

    def create_node(self, key: NodeKeyType, val: NodeValDict) -> List[NodeKeyPair]:
        raise NotImplementedError

    def create_edge(self, key: EdgeKeyType, val: EdgeValDict) -> List[EdgeKeyPair]:
        raise NotImplementedError

    def read_graph(self, key: GraphKeyType) -> GraphType:
        raise NotImplementedError

    def read_node(self, key: NodeKeyType) -> Dict[NodeKeyPair, NodeValDict]:
        raise NotImplementedError

    def read_edge(self, key: EdgeKeyType) -> Dict[EdgeKeyPair, EdgeValDict]:
        raise NotImplementedError

    def update_graph(self, key: GraphKeyType, val: GraphValType) -> List[GraphNameType]:
        raise NotImplementedError

    def update_node(self, key: NodeKeyType, val: NodeValDict) -> List[NodeKeyPair]:
        raise NotImplementedError

    def update_edge(self, key: EdgeKeyType, val: EdgeValDict) -> List[EdgeKeyPair]:
        raise NotImplementedError

    def delete_graph(self, key: GraphKeyType) -> int:
        raise NotImplementedError

    def delete_node(self, key: NodeKeyType) -> int:
        raise NotImplementedError

    def delete_edge(self, key: EdgeKeyType) -> int:
        raise NotImplementedError

    def query(self, query: Text, *args, **kwargs) -> Any:
        """Run query on data source."""
        with self._driver.session() as session:
            return session.run(query)
