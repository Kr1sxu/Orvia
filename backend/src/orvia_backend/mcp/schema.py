"""有限JSON Schema子集；未支持声明明确拒绝，不依赖工具readOnlyHint授予权限。"""
import math
from .protocol import McpError, encode

TYPES={'object':dict,'string':str,'integer':int,'number':(int,float),'boolean':bool,'array':list,'null':type(None)}

def fail(message):raise McpError('MCP_SCHEMA',message)


def _budget(value,depth=0):
    """开放object同样受全局预算约束，additionalProperties不能藏无界结构。"""
    if depth>6:fail('参数正文嵌套超过6层')
    if type(value) is dict:
        if len(value)>32 or any(type(key) is not str or not 1<=len(key)<=100 for key in value):fail('对象字段超出全局预算')
        for item in value.values():_budget(item,depth+1)
    elif type(value) is list:
        if len(value)>64:fail('数组超过64项预算')
        for item in value:_budget(item,depth+1)
    elif type(value) is str:
        if len(value)>8000:fail('字符串超过8000字预算')
        try:value.encode('utf-8')
        except UnicodeError:fail('字符串包含无效Unicode')
    elif type(value) in (int,float):
        if abs(value)>2**53-1 or not math.isfinite(value):fail('数字必须有限且在安全范围内')
    elif value is not None and type(value) is not bool:fail('参数必须为受支持的JSON值')

def validate_schema(schema,depth=0):
    """支持有界常用字段；不接受外部引用、正则、组合表达式或不明约束。"""
    if depth>6 or type(schema) is not dict:fail('schema类型无效或嵌套超过6层')
    kind=schema.get('type')
    if type(kind) is not str or kind not in TYPES:fail('schema必须声明单一受支持类型')
    allowed={'type','title','description','enum','default'}
    for key in ('title','description'):
        if key in schema and (type(schema[key]) is not str or len(schema[key])>1000):fail('schema说明超过预算')
    if kind=='object':
        allowed|={'properties','required','additionalProperties','minProperties','maxProperties'}
        props=schema.get('properties',{});required=schema.get('required',[])
        if type(props) is not dict or len(props)>32 or type(required) is not list or any(type(key) is not str or key not in props for key in required) or len(set(required))!=len(required):fail('object字段或必填项无效')
        for key,value in props.items():
            if not isinstance(key,str) or not 1<=len(key)<=100:fail('object字段名称超过预算')
            validate_schema(value,depth+1)
        if type(schema.get('additionalProperties',False)) is not bool:fail('不支持additionalProperties子schema')
        limits=('minProperties','maxProperties',32)
    elif kind=='array':
        allowed|={'items','minItems','maxItems','uniqueItems'}
        if 'items' not in schema:fail('array必须明确items契约')
        validate_schema(schema['items'],depth+1)
        if type(schema.get('uniqueItems',False)) is not bool:fail('uniqueItems必须是布尔值')
        limits=('minItems','maxItems',64)
    elif kind=='string':
        allowed|={'minLength','maxLength'};limits=('minLength','maxLength',8000)
    elif kind in {'integer','number'}:
        allowed|={'minimum','maximum','exclusiveMinimum','exclusiveMaximum'};limits=None
        for key in ('minimum','maximum','exclusiveMinimum','exclusiveMaximum'):
            value=schema.get(key,0)
            if type(value) not in (int,float) or abs(value)>2**53-1 or not math.isfinite(value):fail('数字schema范围无效')
        if schema.get('minimum',-(2**53-1))>schema.get('maximum',2**53-1):fail('数字范围上下限不一致')
    else:limits=None
    if set(schema)-allowed:fail('schema含不受支持的约束，不能忽略后调用工具')
    if limits:
        low,high,maximum=limits
        if any(key in schema and (type(schema[key]) is not int or not 0<=schema[key]<=maximum) for key in (low,high)) or schema.get(low,0)>schema.get(high,maximum):fail('schema长度预算无效')
    if 'enum' in schema:
        values=schema['enum']
        if type(values) is not list or not 1<=len(values)<=32:fail('enum最多32项')
        shallow={key:value for key,value in schema.items() if key not in {'enum','default'}}
        for value in values:
            _budget(value);_validate(shallow,value,depth)
    if 'default' in schema:
        _budget(schema['default']);_validate({key:value for key,value in schema.items() if key!='default'},schema['default'],depth)
    encode({'schema':schema})

def _validate(schema,value,depth=0):
    if depth>6:fail('值嵌套超过6层')
    kind=schema['type'];expected=TYPES[kind]
    if kind=='number':valid=type(value) in (int,float) and abs(value)<=2**53-1 and math.isfinite(value)
    else:valid=type(value) is expected
    if not valid:fail('参数类型不符合已审查schema')
    if kind=='object':
        props=schema.get('properties',{})
        if len(value)>32 or any(key not in value for key in schema.get('required',[])):fail('对象字段超预算或缺少必填项')
        if not schema.get('additionalProperties',False) and set(value)-set(props):fail('参数包含未审查字段')
        for key in value.keys() & props.keys():_validate(props[key],value[key],depth+1)
        if not schema.get('minProperties',0)<=len(value)<=schema.get('maxProperties',32):fail('对象长度不符合schema')
    elif kind in {'string','array'}:
        low,high,limit=('minLength','maxLength',8000) if kind=='string' else ('minItems','maxItems',64)
        if not schema.get(low,0)<=len(value)<=schema.get(high,limit):fail('字段长度不符合schema或预算')
        if kind=='array':
            for item in value:_validate(schema['items'],item,depth+1)
            if schema.get('uniqueItems') and len({encode({'value':item}) for item in value})!=len(value):fail('数组包含重复项')
    elif kind in {'integer','number'}:
        if abs(value)>2**53-1 or value<schema.get('minimum',-(2**53-1)) or value>schema.get('maximum',2**53-1):fail('数字超出schema或安全范围')
        if ('exclusiveMinimum' in schema and value<=schema['exclusiveMinimum']) or ('exclusiveMaximum' in schema and value>=schema['exclusiveMaximum']):fail('数字违反排他边界')
    if 'enum' in schema and not any(type(value) is type(item) and value==item for item in schema['enum']):fail('参数不在enum范围')

def validate(schema,value):
    """校验输入/结构化输出；未知约束先拒绝，值不会执行代码或跟随URI。"""
    validate_schema(schema)
    _budget(value)
    _validate(schema,value)
    encode({'value':value})
