import sys
import libyang as ly
from typing import Optional
import datetime


DEBUG_ENABLE = False
MODEL_TITLE_SRC = 'openconfig'
MODEL_TITLE_DEST = 'sonic'
ANNOTATION_SUFFIX = '-annot'
DB_TYPE_CONFIG = 'config'
DB_TYPE_STATE = 'state'
DB_NAMES = {DB_TYPE_CONFIG: 'CONFIG_DB', DB_TYPE_STATE: 'STATE_DB'}


class Annotation:
    """
    Parse annotation yang file
    """

    def __init__(self, search_path, yang_file) -> None:
        self.search_path = search_path
        self.yang_file = yang_file
        self.info = {}
        self.tables = []
        self.fields = []
        self.keys = []
        self.dbs = set()
        self.parse()


    def leaf_value(self, content, key) -> Optional[str]:
        pos = content.find(key)
        if pos != -1:
            pos1 = content.find('"', pos) + 1
            pos2 = content.find('"', pos1)
            return content[pos1:pos2].strip()
        
        return None


    def key_xpath(self, deviation, key) -> Optional[list]:
        field_name = self.leaf_value(deviation, key)
        if field_name is None:
            return None
        
        xpath = deviation[:deviation.find('{')].strip()[1:-1]

        # restore the prefix name with module name
        xpath = xpath.replace(self.info['src_module'][1], self.info['src_module'][0])
        for imp in self.info['imports']:
            xpath = xpath.replace(imp[1], imp[0])

        return [xpath, field_name]


    def table_name(self, deviation) -> None:
        table_name = self.leaf_value(deviation, 'sonic-ext:table-name')
        if table_name is None:
            return

        xpath = self.key_xpath(deviation, 'sonic-ext:table-name')[0]

        db_name = self.leaf_value(deviation, 'sonic-ext:db-name')
        if db_name is None or db_name == DB_NAMES[DB_TYPE_CONFIG]:
            self.dbs.add(DB_TYPE_CONFIG)
            self.tables.append([None, table_name, DB_TYPE_CONFIG, DB_NAMES[DB_TYPE_CONFIG]])
        elif db_name == DB_NAMES[DB_TYPE_STATE]:
            self.dbs.add(DB_TYPE_STATE)
            self.tables.append([xpath, table_name, DB_TYPE_STATE, db_name])
        else:
            raise Exception("Not support the db name " + db_name)

        self.fields.append([])

        return


    def key_name(self, deviation) -> None:
        v = self.key_xpath(deviation, 'sonic-ext:field-transformer')
        if v is not None:
            self.keys.append(v[0])

        v = self.key_xpath(deviation, 'sonic-ext:key-transformer')
        if v is None:
            return None

        # change table xpath for precise path for config table
        if self.tables[-1][0] is None:
            self.tables[-1][0] = v[0]


    def field_name(self, deviation) -> None:
        v = self.key_xpath(deviation, 'sonic-ext:field-name')
        if v is None:
            return

        # filter with different table
        for i in range(len(self.tables)):
            if v[0].find(self.tables[i][0]) != -1 and v[0].find(':' + self.tables[i][2] + '/') != -1:
                self.fields[i].append(v)
                break


    def parse(self) -> None:
        """
        Examples for arguments:
        info: list, eg. {'src_module': [yang module name, yang module prefix], 'imports': [[yang module name, yang module prefix], ...]}
        tables: array, eg. [[xpath, table name, table type, db type], ...]
        fields: array, eg. [[[xpath, field name], ...], ...]
        keys: array, eg. [xpath, ...]
        """
        imports = []
        ctx = ly.Context(self.search_path, leafref_extended=True)
        module = ctx.load_module(self.yang_file)
        module_name = module.name()
        for imp in module.imports():
            """
            TODO
            Need a better way to find the original openconfig module name.
            """
            if imp.name() + ANNOTATION_SUFFIX ==  module_name:
                self.info['src_module'] = [imp.name(), imp.prefix()]
            else:
                imports.append([imp.name(), imp.prefix()])
        self.info['imports'] = imports

        debug_print(self.info)

        content = module.print('yang', ly.IOType.MEMORY)
        deviations = content.split(' deviation ')
        for deviation in deviations[1:]:
            deviation = deviation.strip()
            self.table_name(deviation)
            self.key_name(deviation)
            self.field_name(deviation)

        debug_print(self.tables)
        debug_print(self.fields)
        debug_print(self.keys)

class Generator:
    """
    Generate sonic yang file by annotation and open-config yang files.
    """

    def __init__(self, search_path, annot, cfg) -> None:
        self.search_path = search_path
        self.annot = annot
        self.cfg = cfg
        self.ctx = ly.Context(search_path, leafref_extended=True)
        self.module = self.__load_module()
        self.module_name = self.__name()


    def __load_module(self) -> ly.Module:
        for m in self.annot.info['imports']:
            self.ctx.load_module(m[0])

        return self.ctx.load_module(self.annot.info['src_module'][0])

    
    def __name(self) -> str:
        name = self.module.name()
        if name.find(MODEL_TITLE_SRC) == -1:
            raise Exception("Failed to tranform module name. Invalid tranform key: " + MODEL_TITLE_SRC)

        return name.replace(MODEL_TITLE_SRC, MODEL_TITLE_DEST)


    def __to_words(self, xpath) -> str:
        xpath = xpath.replace(self.module.name() + ':', '')
        return xpath[1:xpath.find('/', 1)].replace('-', ' ')


    def namespace(self) -> str:
        return 'namespace "http://github.com/Azure/' + self.module_name + '";'


    def prefix(self, title) -> str:
        prefix = 'prefix '
        words = self.module_name.split('-')

        for wd in words:
            if wd == title:
                prefix += wd
            else:
                prefix += '-'
                prefix += wd[:3]

        prefix += ';'

        return prefix


    def imports(self) -> str:
        return 'import sonic-extension { prefix sonic-ext; }'


    def organization(self) -> str:
        return 'organization "SONiC";'


    def contact(self) -> str:
        return 'contact "SONiC";'


    def description(self) -> str:
        return 'description "' + self.module_name.replace('-', ' ').upper() + '";'


    def revision(self) -> str:
        return 'revision ' + datetime.date.today().strftime('%Y-%m-%d') + '{ description "Initial revision.";}'


    def gen_type(self, type) -> str:
        text = ''
        if type is None:
            return text

        text = 'type '
        is_simple = True

        if type.base() is ly.Type.UNION:
            is_simple = False
            text += type.basename() + '{'
            for utype in type.union_types():
                text += self.gen_type(utype)
            text += '}'
        elif type.base() in ly.Type.STR_TYPES:
            text += ly.Type.BASENAMES[ly.Type.STRING]
        elif type.leafref_type() is not None:
            text += type.leafref_type().basename()
        else:
            text += type.basename()

        # other child types processing
        fraction_digits = type.fraction_digits()
        range = type.range()
        if fraction_digits is not None or range is not None:
            is_simple = False
            text += '{'

            if fraction_digits is not None:
                text += 'fraction-digits ' + str(fraction_digits) + ';'
            if range :
                text += 'range "' + range + '";'

            text += '}'

        if is_simple:
            text += ';'

        return text


    def gen_unit(self, node) -> str:
        text = ''

        if hasattr(node, 'units') and node.units() is not None:
            text += 'units ' + node.units() + ';'

        return text


    def gen_leaf(self, xpath, key) -> str:
        debug_print('leaf xpath: ' + xpath)

        node = next(self.ctx.find_path(xpath))
        node_name = node.name()
 
        # leaf name
        text = 'leaf ' + (node_name if key is None else key) + ' {'
        # leaf description
        text += 'description "' + (node.parent().description() if node_name == 'instant' else node.description()) + '";'
        # leaf basic type
        text += self.gen_type(node.type())
        # leaf units
        text += self.gen_unit(node)

        text += '}'

        return text


    def gen_list(self, index) -> str:
        xpath = self.annot.keys[index]
        debug_print(xpath)

        node = next(self.ctx.find_path(xpath))
        text = ''

        # list key
        key = node.name()
        text += 'key "' + key + '";'
        text += self.gen_leaf(xpath, key)

        for field in self.annot.fields[index]:
            text += self.gen_leaf(field[0], field[1])

        return text


    def gen_container(self, index) -> str:
        name = self.__to_words(self.annot.keys[index])
        text = 'container ' + self.annot.tables[index][1] + ' {'
        # config
        if self.annot.tables[index][2] == DB_TYPE_CONFIG:
            text += 'description "Configuration data for ' + name + 's in ' + self.annot.tables[index][3] + '.";'
        # state
        else:
            text += 'config false;sonic-ext:db-name "' + self.annot.tables[index][3] + '";description "Operational state data for ' + name + 's in ' + self.annot.tables[index][3] + '.";'

        text += 'list ' + self.annot.tables[index][1] + '_LIST {'

        text += self.gen_list(index)

        text += '}}'

        return text


    def gen_head(self) -> str:
        text = 'module ' + self.module_name + ' {'
        text += self.namespace()
        text += self.prefix(MODEL_TITLE_DEST)
        text += self.imports()
        text += self.organization()
        text += self.contact()
        text += self.description()
        text += self.revision()
        text += 'container ' + self.module_name + '{'

        return text
    

    def gen_tables(self) -> str:
        text = ''

        for i in range(len(self.annot.tables)):
            if self.cfg is None or self.annot.tables[i][2] == self.cfg:
                text += self.gen_container(i)

        text += '}}'

        return text
    

    def gen_yang(self) -> str:
        text = self.gen_head()
        text += self.gen_tables()

        debug_print(text)
        return text
    

    def to_file(self, yang, out_dir) -> str:
        ctx = ly.Context(self.search_path)
        module = ctx.parse_module_str(yang)
        text = module.print("yang", ly.IOType.MEMORY)

        debug_print(text)

        path = out_dir.strip()
        if path[-1] != '/':
            path += '/'
        path += self.module_name + '.yang'

        with open(path, 'w') as f:
            f.write(text)

        return path


def debug_print(data):
    if DEBUG_ENABLE:
        print(data)


def sonic_yanggen(search_path, annot_module_name, out_dir, sel_db = None) -> list:
    """
    Automatically generate a sonic annotation yang model to a sonic yang model.

    Inputs:
    search_path: mandatory, yang model search directory, including annotation yang model and dependency models.
    annot_module_name: mandatory, annotation yang module name
    out_dir: mandatory, output directory for target sonic yang model.
    sel_db: optional, None|config|state db selection, default is None selection generating all

    Return: list value or None.
    Example:
    {'name': 'xxxxx', 'type': 'config/state', 'yang': 'xxxxx'}

    """
    # 1. parse the annotation yang file
    annot = Annotation(search_path, annot_module_name)

    # 2. create yang text by source module
    gen = Generator(search_path, annot, sel_db)
    text = gen.gen_yang()

    # 3. format yang text and output file
    path = gen.to_file(text, out_dir)

    print('sonic_yanggen', path)

    # return module name and yang text content for extension
    return {'name': gen.module_name, 'type': sel_db, 'yang': text.replace('\n', '')}


def main(argv):
    """
    argv[1]: mandatory, yang model search directory
    argv[2]: mandatory, annotation yang file module name
    argv[3]: mandatory, output directory for generation file
    argv[4]: optional, None|config|state db selection, default is None selection generating all
    """

    sonic_yanggen(argv[1], argv[2], argv[3], argv[4] if len(argv) > 4 else None)

    # examples
    #sonic_yanggen('/home/sonic/sonic/sonic-buildimage/src/sonic-mgmt-common/models/yang', 'openconfig-optical-attenuator-annot', '/home/sonic/work/test')
    #sonic_yanggen('/home/sonic/sonic/sonic-buildimage/src/sonic-mgmt-common/models/yang', 'openconfig-optical-amplifier-annot', '/home/sonic/work/test')


if __name__ == "__main__":
    main(sys.argv)
