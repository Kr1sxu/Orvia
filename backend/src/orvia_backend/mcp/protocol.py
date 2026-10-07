"""固定MCP2025-06-18与有限JSON消息，错误不携带服务正文或凭据。"""
import json
import math
from ..computer.paths import ToolError

VERSION = '2025-06-18'
WIRE_LIMIT = 64 * 1024
class McpError(ToolError):
    """协议和传输只返回稳定代码与中文说明，不返回原始供应商异常。"""

def _bounded(value, depth=0):
    if depth > 24:
        raise McpError('MCP_JSON', '协议消息嵌套超过24层')
    if isinstance(value, dict):
        if len(value)>128:raise McpError('MCP_JSON','协议对象字段超过128项')
        for key,item in value.items():
            _bounded(key,depth+1);_bounded(item,depth+1)
    elif isinstance(value,list):
        if len(value)>128:raise McpError('MCP_JSON','协议数组超过128项')
        for item in value:_bounded(item,depth+1)
    elif isinstance(value,float) and (not math.isfinite(value) or abs(value)>2**53-1):
        raise McpError('MCP_JSON','协议数字必须有限且在安全范围内')
    elif type(value) is int and abs(value)>2**53-1:
        raise McpError('MCP_JSON','协议整数超出安全范围')
    elif isinstance(value,str):
        try:value.encode('utf-8')
        except UnicodeError:raise McpError('MCP_JSON','协议包含无效Unicode') from None

def decode(payload):
    """严格UTF-8单对象；禁止重复键、NaN、过深数据及超64KiB消息。"""
    try:
        if isinstance(payload,str):payload=payload.encode('utf-8')
        if not isinstance(payload,bytes) or len(payload)>WIRE_LIMIT:
            raise McpError('MCP_LIMIT','协议消息超过64KiB')
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise McpError('MCP_JSON','JSON字段重复')
                result[key]=value
            return result
        def invalid(_):raise McpError('MCP_JSON','JSON禁止非有限数字')
        value=json.loads(payload.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
        if not isinstance(value,dict):raise McpError('MCP_JSON','协议消息必须为单个JSON对象')
        _bounded(value)
        return value
    except (UnicodeError,ValueError,RecursionError):
        raise McpError('MCP_JSON','协议消息不是受支持的UTF-8 JSON') from None

def encode(value):
    """请求在写出前应用同一有限JSON预算，拒绝无效Unicode及非有限值。"""
    try:
        data=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
        decode(data)
        return data
    except (UnicodeError,ValueError,TypeError,RecursionError):
        raise McpError('MCP_JSON','请求不是受支持的有限JSON对象') from None
