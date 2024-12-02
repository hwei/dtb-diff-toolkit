import csv
import os
import re
from typing import NamedTuple

def regex_str_is_simple(regex_str: str) -> bool:
    special_chars = ".^$*+?{}[]\\|()"
    return all(c not in special_chars for c in regex_str)

class SchemaDefine(NamedTuple):
    schema_name: str
    schema_args: tuple[str]

class PhandlePropertyDefines:
    def __init__(self):
        # 相对于当前 py 文件加载 phandle_property_defines.csv
        csv_path = os.path.join(os.path.dirname(__file__), 'phandle_property_defines.csv')

        simple_prop_defines = dict[str, SchemaDefine]()
        self.simple_prop_defines = simple_prop_defines
        regex_prop_defines = list[tuple[re.Pattern, SchemaDefine]]()
        self.regex_prop_defines = regex_prop_defines

        with open(csv_path, 'r') as file:
            reader = csv.reader(file)
            header = next(reader)
            index_prop_name_regex = header.index('prop_name_regex')
            index_schema_name = header.index('schema_name')
            index_schema_args = header.index('schema_args')
            for row in reader:
                prop_name_regex = row[index_prop_name_regex]
                schema_name = row[index_schema_name]
                schema_args = row[index_schema_args]
                schema_define = SchemaDefine(schema_name, tuple(schema_args.split()))
                if regex_str_is_simple(prop_name_regex):
                    simple_prop_defines[prop_name_regex] = schema_define
                else:
                    regex_prop_defines.append((re.compile(prop_name_regex), schema_define))   

    def get_schema(self, prop_name: str) -> SchemaDefine | None:
        if prop_name in self.simple_prop_defines:
            return self.simple_prop_defines[prop_name]
        for regex, verify_func in self.regex_prop_defines:
            if regex.match(prop_name):
                return verify_func
        return None
