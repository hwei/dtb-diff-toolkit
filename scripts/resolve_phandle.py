import sys
import yaml
from phandle_property_defines import PhandlePropertyDefines, SchemaDefine
from typing import Generator, TypeAlias, Callable

def construct_hex(loader, node):
    return [int(n.value, 16) for n in node.value]

yaml.add_constructor('!u64', construct_hex)
yaml.add_constructor('!u8', construct_hex)

class HexInt(int):
    pass

def hexint_representer(dumper, data):
    return dumper.represent_int(hex(data))

yaml.add_representer(HexInt, hexint_representer)

def resolve_flattend_value(node: dict, prop_name: str) -> list[int]:
    l = node[prop_name]
    flattened_value = [v for sublist in l for v in sublist]
    l.clear()
    l.append(flattened_value)
    return flattened_value

ResolvePhandleFunc: TypeAlias = Callable[[int], tuple[str, dict] | None]
def resolve_phandle_cells_args(prop_name: str, node: dict, resolve_phandle_func: ResolvePhandleFunc, provider_cell_name: str, provider_cell_optional = ''):
    value = resolve_flattend_value(node, prop_name)

    i = 0
    while i < len(value):
        phandle_value = value[i]
        provider_path_node = resolve_phandle_func(phandle_value)
        if provider_path_node is None:
            return f'Phandle {phandle_value} not found at cell {i}. Provider cell name: {provider_cell_name} .'
        provider_path, provider_node = provider_path_node
        value[i] = 'p:' + provider_path
        # print(prop_name, i, 'provider_cell_name', provider_cell_name, provider_node.get(provider_cell_name, None))
        if provider_cell_name in provider_node:
            cell_size = provider_node[provider_cell_name][0][0]
            assert isinstance(cell_size, int)
        elif provider_cell_optional:
            cell_size = 0
        else:
            return f'{provider_cell_name} not found in provider node {provider_path} at cell {i}'
        i += 1 + cell_size

def resolve_interrupt_map_args(prop_name: str, node: dict, resolve_phandle_func: ResolvePhandleFunc):
    value = resolve_flattend_value(node, prop_name)

    child_address_cells = node['#address-cells'][0][0]
    child_interrupt_cells = node['#interrupt-cells'][0][0]
    child_cells = child_address_cells + child_interrupt_cells
    assert isinstance(child_cells, int)
    i = 0
    while i < len(value):
        i += child_cells
        phandle_value = value[i]
        provider_path_node = resolve_phandle_func(phandle_value)
        if provider_path_node is None:
            return f'Phandle {phandle_value} not found at cell {i} in interrupt-map.'
        provider_path, provider_node = provider_path_node
        value[i] = 'p:' + provider_path
        if '#address-cells' not in provider_node:
            return f'provider node {provider_path} has no #address-cells property at cell {i} in interrupt-map.'
        parent_address_cells = provider_node['#address-cells'][0][0]
        if '#interrupt-cells' not in provider_node:
            return f'provider node {provider_path} has no #interrupt-cells property at cell {i} in interrupt-map.'
        parent_interrupt_cells = provider_node['#interrupt-cells'][0][0]
        parent_cells = parent_address_cells + parent_interrupt_cells
        assert isinstance(parent_cells, int)
        i += 1 + parent_cells

def resolve_interrupts_args(prop_name: str, node: dict, resolve_phandle_func: ResolvePhandleFunc):
    if 'interrupt-affinity' in node or "interrupt-names" in node:
        # 这种情况下，不需要解析 phandle
        return

    value = resolve_flattend_value(node, prop_name)
    
    for i in range(3, len(value), 4):
        phandle_value = value[i]
        if phandle_value == 0:
            # 0 表示没有中断
            continue
        provider_path_node = resolve_phandle_func(phandle_value)
        if provider_path_node is None:
            return f'Phandle {phandle_value} not found at cell {i} in interrupts.'
        provider_path, provider_node = provider_path_node
        value[i] = 'p:' + provider_path

def resolve_phandle_pattern_args(prop_name: str, node: dict, resolve_phandle_func: ResolvePhandleFunc, pattern: str):
    value = resolve_flattend_value(node, prop_name)
    for i in range(len(value)):
        t = pattern[i % len(pattern)]
        if t == 'P':
            phandle_value = value[i]
            provider_path_node = resolve_phandle_func(phandle_value)
            if provider_path_node is None:
                return f'Phandle {phandle_value} not found at cell {i} with phandle-pattern {pattern} .'
            provider_path, provider_node = provider_path_node
            value[i] = 'p:' + provider_path

resolve_func_map = {
    'phandle_cells': resolve_phandle_cells_args,
    'interrupt_map': resolve_interrupt_map_args,
    'interrupts': resolve_interrupts_args,
    'phandle_pattern': resolve_phandle_pattern_args,
}

class MyRepresenter(yaml.representer.SafeRepresenter):
    def represent_list(self, data):
        # 检查数组中的所有元素是否都是整数
        if all(isinstance(item, int) for item in data):
            # 都是整数，就排成一行
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        else:
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)

yaml.add_representer(list, MyRepresenter.represent_list)

class PhandleResolver:
    def __init__(self):
        self.phandle_to_path_node = dict[int, tuple[str, dict]]()
        self.used_phandles = set[int]()
    
    def collect_phandle_to_path_node(self, node: dict, path: str) -> None:
        if 'phandle' in node:
            phandle_value = node['phandle'][0][0]
            if phandle_value in self.phandle_to_path_node:
                raise ValueError(f'duplicate phandle {phandle_value}')
            self.phandle_to_path_node[phandle_value] = (path or '/', node)
        for key in list(node.keys()):
            value = node[key]
            if isinstance(value, dict):
                self.collect_phandle_to_path_node(value, f'{path}/{key}')
    
    def resolve_path_node(self, phandle_value: int) -> tuple[str, dict] | None:
        if phandle_value in self.phandle_to_path_node:
            r = self.phandle_to_path_node[phandle_value]
            self.used_phandles.add(phandle_value)
            return r

    def get_unused_phandles(self) -> set[int]:
        return self.phandle_to_path_node.keys() - self.used_phandles

def resolve_dts_phandle(
        output_dts_yaml_file: str, input_dts_yaml_file: str):

    phandlePhandleResolver = PhandleResolver()
    phandle_property_defines = PhandlePropertyDefines()

    # (prop_name: str, node: dict) -> None
    ResolveFunction: TypeAlias = Callable[[str, dict], str | None]
    resolve_func_cache = dict[SchemaDefine, ResolveFunction]()
    def get_resolve_func(prop_name: str) -> ResolveFunction | None:
        schema_define = phandle_property_defines.get_schema(prop_name)
        if schema_define is None:
            return None
        if schema_define in resolve_func_cache:
            return resolve_func_cache[schema_define]

        resolve_func = resolve_func_map[schema_define.schema_name]
        f = lambda prop_name, node: resolve_func(prop_name, node, phandlePhandleResolver.resolve_path_node, *schema_define.schema_args)
        resolve_func_cache[schema_define] = f
        return f

    def replace_phandle_in_node(node: dict[str, any], node_path: str, ignore_disabled: bool) -> Generator[str, None, None]:
        # 删除 phandle 属性
        if 'phandle' in node:
            del node['phandle']
        for key, value in node.items():
            if isinstance(value, dict):
                if ignore_disabled and 'compatible' in value and 'status' in value:
                    if value['status'][0] == 'disabled':
                        # 如果节点是 disabled 的，就不需要解析 phandle 了
                        continue

                for err_msg in replace_phandle_in_node(value, f'{node_path}/{key}', ignore_disabled):
                    yield err_msg
            elif isinstance(value, list):
                resolve_func = get_resolve_func(key)
                if resolve_func is not None:
                    err_msg = resolve_func(key, node)
                    if err_msg is not None:
                        yield f'{node_path}/{key}: {err_msg}'

    with open(input_dts_yaml_file, 'r') as file:
        data = yaml.load(file, Loader=yaml.Loader)

    root_node = data[0]

    # 把特殊节点从 root_node 移除，保存到 special_nodes 中
    special_node_names = ['aliases', '__symbols__']
    special_nodes = dict[str, dict]()
    for name in special_node_names:
        if name in root_node:
            special_nodes[name] = root_node[name]
            del root_node[name]    

    phandlePhandleResolver.collect_phandle_to_path_node(root_node, '')

    anyError = False

    # 替换 phandle
    for err_msg in replace_phandle_in_node(root_node, '', False):
        print(err_msg)
        anyError = True
    
    # 检查是否有未使用的 phandle
    path_to_symbol = dict[str, str]()
    if '__symbols__' in special_nodes:
        for symbol, value in special_nodes['__symbols__'].items():
            assert isinstance(value, list)
            assert len(value) == 1
            path = value[0]
            assert isinstance(path, str)
            path_to_symbol[path] = symbol
    for unused_phandle in phandlePhandleResolver.get_unused_phandles():
        path, _ = phandlePhandleResolver.phandle_to_path_node[unused_phandle]
        if path in path_to_symbol:
            # 如果是 __symbols__ 中的节点，就不报错
            continue
        print(f'Unused phandle 0x{unused_phandle:02x} at {path}')
        anyError = True

    # 把特殊节点重新加回去
    for name, node in special_nodes.items():
        root_node[name] = node

    # 把 phandle 映射表加到根节点
    phandle_mapping = dict[HexInt, str]()
    for phandle, (path, node) in phandlePhandleResolver.phandle_to_path_node.items():
        phandle_mapping[HexInt(phandle)] = path
    root_node['__phandle_mapping__'] = phandle_mapping
    
    with open(output_dts_yaml_file, 'w') as file:
        yaml.dump(data, file, Dumper=yaml.Dumper)

    if anyError:
        sys.exit(1)


if __name__ == '__main__':
    resolve_dts_phandle(sys.argv[1], sys.argv[2])
