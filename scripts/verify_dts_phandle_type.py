import yaml
import sys
from typing import TypeAlias, Callable
from phandle_property_defines import PhandlePropertyDefines, SchemaDefine

class phandle:
    def __init__(self, value: int):
        self.value = value

def construct_phandle(loader, node):
    return phandle(int(node.value, 16))

yaml.add_constructor('!phandle', construct_phandle)

def construct_hex(loader, node):
    return [int(n.value, 16) for n in node.value]

yaml.add_constructor('!u64', construct_hex)
yaml.add_constructor('!u8', construct_hex)


def verify_phandle_cells_args(prop_name: str, node: dict, phandle_to_path_node: dict[int, tuple[str, dict]], provider_cell_name: str, provider_cell_optional = ''):
    prop_value = [v for sublist in node[prop_name] for v in sublist]
    i = 0

    while i < len(prop_value):
        if not isinstance(prop_value[i], phandle):
            raise ValueError(f'cell {i} is not a phandle')
        phandle_value = prop_value[i].value
        if phandle_value not in phandle_to_path_node:
            raise ValueError(f'phandle {phandle_value} not found')
        provider_path, provider_node = phandle_to_path_node[phandle_value]
        if provider_cell_name in provider_node:
            cell_size = provider_node[provider_cell_name][0][0]
            assert isinstance(cell_size, int)
        elif provider_cell_optional:
            cell_size = 0
        else:
            raise ValueError(f'{provider_cell_name} not found in provider node {provider_path}')
        for j in range(i + 1, i + 1 + cell_size):
            if j >= len(prop_value):
                raise ValueError(f'not enough cells for {provider_cell_name}')
            if not isinstance(prop_value[j], int):
                raise ValueError(f'cell {j} is not an integer')
        i += 1 + cell_size

def verify_interrupt_map_args(prop_name: str, node: dict, phandle_to_path_node: dict[int, tuple[str, dict]]):
    child_address_cells = node['#address-cells'][0][0]
    child_interrupt_cells = node['#interrupt-cells'][0][0]
    child_cells = child_address_cells + child_interrupt_cells
    assert isinstance(child_cells, int)
    prop_value = [v for sublist in node['interrupt-map'] for v in sublist]
    i = 0
    while i < len(prop_value):
        i += child_cells
        if not isinstance(prop_value[i], phandle):
            raise ValueError(f'cell {i} is not a phandle')
        phandle_value = prop_value[i].value
        if phandle_value not in phandle_to_path_node:
            raise ValueError(f'phandle {phandle_value} not found')
        parent_path, parent_node = phandle_to_path_node[phandle_value]
        parrent_address_cells = parent_node['#address-cells'][0][0]
        parrent_interrupt_cells = parent_node['#interrupt-cells'][0][0]
        parent_cells = parrent_address_cells + parrent_interrupt_cells
        assert isinstance(parent_cells, int)
        for j in range(i + 1, i + 1 + parent_cells):
            if j >= len(prop_value):
                raise ValueError(f'not enough cells for parent node {parent_path}')
            if not isinstance(prop_value[j], int):
                raise ValueError(f'cell {j} is not an integer')
        i += 1 + parent_cells

def verify_interrupts_args(prop_name: str, node: dict, phandle_to_path_node: dict[int, tuple[str, dict]]):
    prop_values = [v for sublist in node[prop_name] for v in sublist]
    if 'interrupt-affinity' in node or "interrupt-names" in node:
        for i, v in enumerate(prop_values):
            if not isinstance(v, int):
                raise ValueError(f'cell {i} is not an integer')
        return
    
    for i, v in enumerate(prop_values):
        if i % 4 == 3:
            if not isinstance(v, phandle) and v != 0:
                raise ValueError(f'cell {i} is not a phandle')
        else:
            if not isinstance(v, int):
                raise ValueError(f'cell {i} is not an integer')

def verify_phandle_pattern_args(prop_name: str, node: dict, phandle_to_path_node: dict[int, tuple[str, dict]], pattern: str):
    prop_values = [v for sublist in node[prop_name] for v in sublist]

    for i, v in enumerate(prop_values):
        t = pattern[i % len(pattern)]
        if t == 'P':
            if not isinstance(v, phandle):
                raise ValueError(f'cell {i} is not a phandle')
        elif t == 'I':
            if not isinstance(v, int):
                raise ValueError(f'cell {i} is not an integer')
        else:
            raise ValueError(f'unknown pattern {pattern}')

verify_func_map = {
    'phandle_cells': verify_phandle_cells_args,
    'interrupt_map': verify_interrupt_map_args,
    'interrupts': verify_interrupts_args,
    'phandle_pattern': verify_phandle_pattern_args,
}

def verify_dts_phandle_type(input_dts_yaml_path: str):
    def int_value_to_type_name(value):
        if isinstance(value, phandle):
            return 'P'
        elif isinstance(value, int):
            return 'I'
        else:
            raise ValueError(f'Unknown value type: {type(value)}')

    def transform_prop_value_to_type(prop_value) -> str | None:
        if isinstance(prop_value, bool):
            return None
        assert isinstance(prop_value, list)
        if isinstance(prop_value[0], str):
            return None
        assert isinstance(prop_value[0], list)
        # flatten
        prop_type = ''.join(int_value_to_type_name(v) for sublist in prop_value for v in sublist)
        if 'P' not in prop_type:
            return None
        else:
            return prop_type

    def any_phandle(prop_type):
        if isinstance(prop_type, list):
            for t in prop_type:
                if any_phandle(t):
                    return True
        return prop_type == 'P'

    phandle_to_path_node = dict[int, tuple[str, dict]]()
    phandle_property_defines = PhandlePropertyDefines()
    VerifyFunction: TypeAlias = Callable[[str, dict], None]
    verify_func_cache = dict[SchemaDefine, VerifyFunction]()
    def get_verify_func(prop_name: str) -> VerifyFunction | None:
        schema_define = phandle_property_defines.get_schema(prop_name)
        if schema_define is None:
            return None
        if schema_define in verify_func_cache:
            return verify_func_cache[schema_define]

        verify_func = verify_func_map[schema_define.schema_name]
        f = lambda prop_name, node: verify_func(prop_name, node, phandle_to_path_node, *schema_define.schema_args)
        verify_func_cache[schema_define] = f
        return f

    def collect_phandle_to_path_node(path: str, node: dict):
        if 'phandle' in node:
            phandle_value = node['phandle'][0][0]
            if phandle_value in phandle_to_path_node:
                raise ValueError(f'duplicate phandle {phandle_value}')
            phandle_to_path_node[phandle_value] = (path or '/', node)
        for key, value in node.items():
            if isinstance(value, dict):
                collect_phandle_to_path_node(f'{path}/{key}', value)

    def verify_prop_type(node_path: str, prop_node: dict[str, any], parent_prop_path: str):
        if 'status' in prop_node and prop_node['status'][0] == 'disabled':
            return

        for key, value in prop_node.items():
            if key == 'compatible':
                continue

            prop_path = f'{parent_prop_path}/{key}'

            if isinstance(value, dict):
                next_node_path = f'{node_path}/{key}'
                if 'compatible' in value:
                    # 一个新的 node
                    for e in verify_prop_type(next_node_path, value, ''):
                        yield e
                else:
                    # 当前 node 的嵌套属性
                    for e in verify_prop_type(node_path, value, prop_path):
                        yield e
            else:
                verify_func = get_verify_func(key)
                if verify_func:
                    # 已知的 Phandle 属性，用已知的规则验证
                    assert isinstance(value, list)
                    e = None
                    try:
                        verify_func(key, prop_node)
                    except ValueError as e1:
                        e = e1
                    if e:
                        yield ValueError(f'Error in {node_path}:{prop_path}: {e}')
                else:
                    # 未知的 Phandle 属性，记录下来
                    prop_type = transform_prop_value_to_type(value)
                    if prop_type:
                        yield ValueError(f'Unknown phandle property {node_path}:{prop_path}: {prop_type}')

    
    with open(input_dts_yaml_path, 'r') as file:
        data = yaml.load(file, Loader=yaml.Loader)
    root_node = data[0]
    collect_phandle_to_path_node('', root_node)
    any_error = False
    for e in verify_prop_type('', root_node, ''):
        print(e)
        any_error = True
    if any_error:
        sys.exit(1)

if __name__ == '__main__':
    verify_dts_phandle_type(sys.argv[1])
