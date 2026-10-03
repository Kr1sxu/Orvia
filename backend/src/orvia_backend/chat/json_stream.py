"""M20 JSON 回答增量：只展示顶层 answer，完整校验前始终是临时文字。"""

import json


class JSONStreamError(ValueError):
    """不包含模型正文的固定增量解析错误。"""

    def __init__(self):
        super().__init__("INVALID_JSON_STREAM")


class AnswerJSONStream:
    """处理任意切块、JSON 转义和 UTF-16 代理对，不把 claims/原始 JSON 当正文。

    feed 返回这次实际新增的解码 answer。finish 必须在供应商真实终态后调用；
    它拒绝重复键（包括嵌套对象）、非法 JSON、未闭合或不一致文字。
    返回的对象仍需 M15 verify_generated 做引用/结论结构校验；本类不授予权限。
    """

    def __init__(self, *, max_answer_chars: int = 2200, max_bytes: int = 65536):
        if type(max_answer_chars) is not int or not 1 <= max_answer_chars <= 65536:
            raise ValueError("回答预算无效")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 65536:
            raise ValueError("JSON 字节预算无效")
        self.max_answer_chars, self.max_bytes = max_answer_chars, max_bytes
        self.raw = ""
        self.answer = ""
        self._bytes = 0
        self._state = "start"
        self._string = "normal"
        self._string_target = None
        self._unicode = ""
        self._high = None
        self._key = ""
        self._keys = set()
        self._nested = []
        self._failed = False

    def _fail(self):
        self._failed = True
        raise JSONStreamError()

    def feed(self, delta: str) -> str:
        """调用方只传真实模型 content 增量；不接受工具参数或完成后的模拟打字。"""
        if self._failed or not isinstance(delta, str):
            self._fail()
        try:
            self._bytes += len(delta.encode("utf-8"))
        except UnicodeError:
            self._fail()
        if self._bytes > self.max_bytes:
            self._fail()
        self.raw += delta
        output = []
        for char in delta:
            if self._string_target is not None:
                decoded, closed = self._string_char(char)
                if decoded:
                    if self._string_target == "key":
                        self._key += decoded
                    elif self._string_target == "answer":
                        self.answer += decoded
                        if len(self.answer) > self.max_answer_chars:
                            self._fail()
                        output.append(decoded)
                if closed:
                    target = self._string_target
                    self._string_target = None
                    if target == "key":
                        if self._key in self._keys:
                            self._fail()
                        self._keys.add(self._key)
                        self._state = "colon"
                    elif target == "nested":
                        self._state = "nested"
                    else:
                        self._state = "after_value"
                continue
            if self._state == "start":
                if char.isspace():
                    continue
                if char != "{":
                    self._fail()
                self._state = "key_or_end"
            elif self._state in {"key_or_end", "key"}:
                if char.isspace():
                    continue
                if char == "}" and self._state == "key_or_end":
                    self._state = "done"
                elif char == '"':
                    self._key = ""
                    self._begin_string("key")
                else:
                    self._fail()
            elif self._state == "colon":
                if char.isspace():
                    continue
                if char != ":":
                    self._fail()
                self._state = "value"
            elif self._state == "value":
                if char.isspace():
                    continue
                if self._key == "answer":
                    if char != '"':
                        self._fail()
                    self._begin_string("answer")
                elif char == '"':
                    self._begin_string("other")
                elif char in "[{":
                    self._nested = [char]
                    self._state = "nested"
                elif char in ",}":
                    self._fail()
                else:
                    # 原始数字/布尔/null 的合法性由 finish 的完整 JSON 校验决定。
                    self._state = "primitive"
            elif self._state == "primitive":
                if char in ",}":
                    self._state = "key" if char == "," else "done"
            elif self._state == "nested":
                if char == '"':
                    self._begin_string("nested")
                elif char in "[{":
                    self._nested.append(char)
                    if len(self._nested) > 64:
                        self._fail()
                elif char in "]}":
                    if not self._nested or (self._nested[-1], char) not in {("[", "]"), ("{", "}")}:
                        self._fail()
                    self._nested.pop()
                    if not self._nested:
                        self._state = "after_value"
            elif self._state == "after_value":
                if char.isspace():
                    continue
                if char == ",":
                    self._state = "key"
                elif char == "}":
                    self._state = "done"
                else:
                    self._fail()
            elif self._state == "done" and not char.isspace():
                self._fail()
        return "".join(output)

    def _begin_string(self, target):
        self._string_target = target
        self._string = "normal"
        self._unicode = ""
        self._high = None

    def _string_char(self, char):
        """高代理先缓存，直到相邻低代理完整到达才显示一个 Unicode 码点。"""
        if self._string in {"hex", "low_hex"}:
            if char not in "0123456789abcdefABCDEF":
                self._fail()
            self._unicode += char
            if len(self._unicode) < 4:
                return "", False
            code = int(self._unicode, 16)
            self._unicode = ""
            if self._string == "low_hex":
                if not 0xDC00 <= code <= 0xDFFF:
                    self._fail()
                value = chr(0x10000 + (self._high - 0xD800) * 0x400 + code - 0xDC00)
                self._high = None
                self._string = "normal"
                return value, False
            if 0xD800 <= code <= 0xDBFF:
                self._high = code
                self._string = "low_slash"
                return "", False
            if 0xDC00 <= code <= 0xDFFF:
                self._fail()
            self._string = "normal"
            return chr(code), False
        if self._string == "low_slash":
            if char != "\\":
                self._fail()
            self._string = "low_u"
            return "", False
        if self._string == "low_u":
            if char != "u":
                self._fail()
            self._string = "low_hex"
            return "", False
        if self._string == "escape":
            if char == "u":
                self._string = "hex"
                return "", False
            escapes = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
            if char not in escapes:
                self._fail()
            self._string = "normal"
            return escapes[char], False
        if char == "\\":
            self._string = "escape"
            return "", False
        if char == '"':
            return "", True
        if ord(char) < 0x20 or 0xD800 <= ord(char) <= 0xDFFF:
            self._fail()
        return char, False

    def finish(self) -> dict:
        """终态只返回完整严格 JSON；最终引用/语义边界由现有业务校验负责。"""
        if self._failed or self._state != "done" or self._string_target is not None or "answer" not in self._keys:
            self._fail()
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise JSONStreamError()
                result[key] = value
            return result
        def valid_unicode(value):
            if isinstance(value, str):
                return not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
            if isinstance(value, dict):
                return all(valid_unicode(key) and valid_unicode(item) for key, item in value.items())
            if isinstance(value, list):
                return all(valid_unicode(item) for item in value)
            return True
        try:
            value = json.loads(self.raw, object_pairs_hook=unique,
                               parse_constant=lambda _: (_ for _ in ()).throw(JSONStreamError()))
            if (not isinstance(value, dict) or not isinstance(value.get("answer"), str)
                    or value["answer"] != self.answer or not valid_unicode(value)):
                self._fail()
            return value
        except (ValueError, TypeError, RecursionError):
            self._fail()
