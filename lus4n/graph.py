import os
import json
import xxhash
import networkx as nx

from tqdm import tqdm
from loguru import logger
from luaparser import ast
from luaparser.astnodes import *
from luaparser.utils.visitor import *
from luaparser.printers import PythonStyleVisitor
from luaparser.builder import SyntaxException


def scan_one_file(file_path: str, _format="json", _debug=False):
    if not os.path.exists(file_path):
        logger.warning(f"{file_path} not existed")
        exit(1)
    try:
        source = open(file_path, "rb").read().decode('latin-1')
        tree = ast.parse(source)
    except SyntaxException:
        return file_path, {}, []
    _visitor = Lus4nVisitor(4, source)
    _visitor.visit(tree)
    call_graph, require = _visitor.output(_format=_format)
    # logger.success(f"Wow! {file_path} done")
    return file_path, call_graph, require


def scan_path(dirt_path: str, _format, _debug=False):
    whole_call_graph = {}
    whole_call_network = nx.DiGraph()
    will_scan = []
    for path, dir_list, file_list in os.walk(dirt_path):
        for file_name in file_list:
            file_path = os.path.join(path, file_name)
            try:
                content = open(file_path, "rb").read()
                if file_path.endswith(".lua") and not content.startswith(b"\x1bL"):
                    will_scan.append(file_path)
                elif content.startswith(b"#!/usr/bin/lua"):
                    will_scan.append(file_path)
            except PermissionError:
                logger.warning(f"PermissionError with {file_path}")
            except Exception as e:
                logger.warning(f"UnknownError with {file_path} [{e}]")
            # except Exception as e:
            #     logger.warning(f"Oops, {file_path} failed by {e}")
    for file_path in tqdm(will_scan):
        _, call_graph, require = scan_one_file(file_path, _format, _debug)
        relative_file_path = file_path[len(dirt_path):]
        if not relative_file_path.startswith("/"):
            relative_file_path = "/" + relative_file_path
        whole_call_graph[relative_file_path] = call_graph
        whole_call_network.add_node(relative_file_path, role='file')
        package_name = os.path.basename(file_path).replace(".lua", "")
        for tmp_name in call_graph.keys():
            if tmp_name == "[G]":
                default_main = f"{package_name}.main.{xxhash.xxh32(file_path).hexdigest()}"
                for called in call_graph["[G]"]:
                    whole_call_network.add_edge(relative_file_path, default_main, action='export')
                    whole_call_network.add_edge(default_main, called, action="call")
            if tmp_name.startswith("[X]"):
                exported = tmp_name.replace("[X]", "")
                sub_names = exported.split('.')
                if len(sub_names) > 1:
                    father = sub_names[0]
                    left = exported[len(father):]
                    # TODO: 或许也可以用M./_M.来筛选导出函数？
                    _exported = f"{package_name}{left}" if father not in require else exported
                else:
                    _exported = exported
                whole_call_network.add_edge(relative_file_path, _exported, action="export")
                for called in call_graph[tmp_name]:
                    whole_call_network.add_edge(_exported, called, action='call')
            if tmp_name.startswith("[L]"):
                defined = tmp_name.replace("[L]", "")
                whole_call_network.add_edge(relative_file_path, defined, action="define")
                for called in call_graph[tmp_name]:
                    whole_call_network.add_edge(defined, called, action='call')
    return whole_call_graph, whole_call_network


class Lus4nVisitor(PythonStyleVisitor):

    def __init__(self, indent, source):
        super().__init__(indent)
        self.source = source
        self.lines = [line.strip() for line in self.source.split('\n')]
        self.stack_for_function = []
        self.call_graph = {}
        self.require = []

    @visitor(str)
    def visit(self, node):
        return repr(node)

    @visitor(float)
    def visit(self, node):
        return str(node)

    @visitor(int)
    def visit(self, node):
        return str(node)

    @visitor(Enum)
    def visit(self, node):
        return str(node.name)

    def indent_str(self, newLine=True):
        res = " " * self.currentIndent
        if newLine:
            res = "\n" + res
        return res

    def indent(self):
        self.currentIndent += self.indentValue

    def dedent(self):
        self.currentIndent -= self.indentValue

    @staticmethod
    def pretty_count(node, is_list=False):
        res = ""
        if isinstance(node, list):
            item_count = len(node)
            res += "[] " + str(item_count) + " "
            if item_count > 1:
                res += "items"
            else:
                res += "item"
        elif isinstance(node, Node):
            if is_list:
                return "{} 1 key"
            key_count = len(
                [attr for attr in node.__dict__.keys() if not attr.startswith("_")]
            )
            res += "{} " + str(key_count) + " "
            if key_count > 1:
                res += "keys"
            else:
                res += "key"
        else:
            res += "[unknow]"
        return res

    @visitor(list)
    def visit(self, obj):
        res = ""
        k = 0
        for itemValue in obj:
            res += (
                    self.indent_str() + str(k) + ": " + self.pretty_count(itemValue, True)
            )
            self.indent()
            res += self.indent_str(False) + self.visit(itemValue)
            self.dedent()
            k += 1
        return res

    @visitor(Node)
    def visit(self, node):
        res = self.indent_str() + node.display_name + ": " + self.pretty_count(node)

        self.indent()

        # comments
        comments = node.comments
        if comments:
            res += self.indent_str() + "comments" + ": " + self.pretty_count(comments)
            k = 0
            self.indent()
            for c in comments:
                res += self.indent_str() + str(k) + ": " + self.visit(c.s)
                k += 1
            self.dedent()

        if isinstance(node, Function) or isinstance(node, LocalFunction):
            name = []
            func_name = self.walk_func_name(node.name, name)
            if isinstance(node, Function):
                self.stack_for_function.append(f"[X]{'.'.join(func_name)}")
            elif isinstance(node, LocalFunction):
                self.stack_for_function.append(f"[L]{'.'.join(func_name)}")

        for attr, attrValue in node.__dict__.items():

            if isinstance(node, Call):
                if len(self.stack_for_function) > 0:
                    from_where = self.stack_for_function[-1]
                else:
                    from_where = "[G]"
                if from_where not in self.call_graph.keys():
                    self.call_graph[from_where] = []
                if isinstance(node.func, Index):
                    try:
                        called_func_name = self.source[node.func.start_char: node.func.stop_char + 1]
                        self.call_graph[from_where].append(called_func_name)
                    except TypeError as e:
                        logger.warning(f"Oops, TypeError {e}")
                    # logger.debug(f"Index: {from_where} -> {self.source[node.func.start_char: node.func.stop_char + 1]}")
                elif isinstance(node.func, Name):
                    self.call_graph[from_where].append(node.func.id)
                    if node.func.id == "require" and len(node.args) > 0 and hasattr(node.args[0], "s"):
                        self.require.append(node.args[0].s)
                    # logger.debug(f"Name: {from_where} -> {node.func.id}")

            if not attr.startswith(("_", "comments")):
                if isinstance(attrValue, Node) or isinstance(attrValue, list):
                    res += (
                            self.indent_str() + attr + ": " + self.pretty_count(attrValue)
                    )
                    self.indent()
                    res += self.visit(attrValue)
                    self.dedent()
                else:
                    if attrValue is not None:
                        res += self.indent_str() + attr + ": " + self.visit(attrValue)

        if isinstance(node, Function) or isinstance(node, LocalFunction):
            self.stack_for_function.pop()

        self.dedent()
        return res

    def output(self, _format="json"):
        for from_where in self.call_graph.keys():
            self.call_graph[from_where] = list(set(self.call_graph[from_where]))
        if _format == "json":
            logger.success(json.dumps(self.call_graph, indent=4))
        return self.call_graph, self.require

    def walk_func_name(self, node: Node, name: list):
        if isinstance(node, Name):
            name.append(node.id)
            return name
        elif isinstance(node, Index):
            name = self.walk_func_name(node.value, name)
            name.append(node.idx.id)
            return name
