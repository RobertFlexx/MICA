"""Strict lowering of a small, unoptimized LLVM IR subset to the MICA32 ABI."""

import re


class Unsupported(ValueError):
    pass


def split(text):
    parts, start, depth = [], 0, 0
    for index, char in enumerate(text):
        depth += char in "[{("
        depth -= char in "]})"
        if char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    return parts + [text[start:].strip()]


def typed(text):
    text = text.strip()
    match = re.match(r"(i(?:1|8|16|32)|ptr|void|%[\w.]+)\b", text)
    if match:
        return match[1], text[match.end():].strip()
    if text.startswith(("[", "{")):
        depth = 0
        for index, char in enumerate(text):
            depth += char in "[{"
            depth -= char in "]}"
            if depth == 0:
                return text[:index + 1], text[index + 1:].strip()
    raise Unsupported("unsupported type: " + text)


def value(text):
    # Clang's scalar parameter and memory alignment attributes carry no data.
    _, rest = typed(text)
    # Strip GEP attributes and other known Clang attributes
    rest = re.sub(r"\b(?:inbounds|nuw|nsw|noundef|signext|zeroext|nonnull|nocapture|readonly|writeonly)\b|\balign \d+\b", "", rest).strip()
    if not re.fullmatch(r"[%@][\w.]+|-?\d+|true|false|null", rest):
        raise Unsupported("unsupported value/attribute: " + text)
    return rest


def align(n, boundary):
    return (n + boundary - 1) // boundary * boundary


class Module:
    def __init__(self, text, multiply=True):
        if 'target datalayout = "e-' not in text or 'target triple = "riscv32-' not in text:
            raise Unsupported("expected little-endian 32-bit Clang IR")
        self.types, self.functions, self.globals, self.external = {}, [], [], []
        self.multiply = multiply
        lines = iter(text.splitlines())
        for line in lines:
            line = line.strip()
            if match := re.fullmatch(r"(%[\w.]+) = type (.+)", line):
                self.types[match[1]] = match[2]
            elif line.startswith("define "):
                if " internal " in line or " private " in line:
                    raise Unsupported("unsupported internal linkage")
                match = re.fullmatch(r"define (?:[\w]+ )*(i32|i16|i8|void|ptr) @([\w.]+)\((.*?)\).*\{", line)
                if not match:
                    raise Unsupported("unsupported function signature: " + line)
                body = []
                for instruction in lines:
                    if instruction.strip() == "}":
                        break
                    instruction = instruction.split(";", 1)[0].strip()
                    instruction = re.sub(r", ![\w.]+ !\d+.*$", "", instruction)
                    if instruction:
                        body.append(instruction)
                self.functions.append((match[2], match[1], split(match[3]) if match[3] else [], body))
            elif line.startswith("declare "):
                match = re.search(r"@([\w.]+)\(", line)
                if not match:
                    raise Unsupported(line)
                if not match[1].startswith("llvm."):
                    self.external.append(match[1])
            elif line.startswith("@"):
                match = re.fullmatch(r"@([\w.]+) = (.*?)\b(global|constant) (.+)", line)
                if not match:
                    raise Unsupported("unsupported global: " + line)
                name, attrs, _, data = match.groups()
                if "internal" in attrs or "private" in attrs:
                    raise Unsupported("unsupported internal global linkage")
                ty, rest = typed(data)
                if "external" in attrs:
                    self.external.append(name)
                else:
                    if re.search(r"\b(thread_local|addrspace|section|comdat)\b", line):
                        raise Unsupported("unsupported global storage: " + line)
                    attributes = split(rest)
                    boundary = self.layout(ty)[1]
                    for attribute in attributes[1:]:
                        if not re.fullmatch(r"align \d+", attribute):
                            raise Unsupported("unsupported global attribute: " + attribute)
                        boundary = int(attribute.split()[1])
                        if boundary < 1 or boundary > 4096 or boundary & (boundary - 1):
                            raise Unsupported("unsupported global alignment")
                    self.globals.append((name, ty, attributes[0], boundary))
            elif line and not line.startswith((";", "source_filename", "target ", "attributes ", "!")):
                raise Unsupported("unsupported module directive: " + line)

    def resolve(self, ty):
        return self.types[ty] if ty in self.types else ty

    def members(self, ty):
        ty = self.resolve(ty)
        if ty.startswith("{"):
            return split(ty[1:-1])
        return None

    def layout(self, ty):
        ty = self.resolve(ty)
        if ty in ("i1", "i8", "i16", "i32", "ptr"):
            size = 4 if ty == "ptr" else max(1, int(ty[1:]) // 8)
            return size, size
        if match := re.fullmatch(r"\[(\d+) x (.+)\]", ty):
            size, boundary = self.layout(match[2])
            return int(match[1]) * size, boundary
        if fields := self.members(ty):
            size, boundary = 0, 1
            for field in fields:
                n, a = self.layout(field)
                size, boundary = align(size, a) + n, max(boundary, a)
            return align(size, boundary), boundary
        raise Unsupported("unsupported layout: " + ty)

    def initializer(self, ty, initial):
        size, _ = self.layout(ty)
        if initial == "zeroinitializer":
            return bytes(size)
        resolved = self.resolve(ty)
        if resolved.startswith("i"):
            return (int(initial) & ((1 << (size * 8)) - 1)).to_bytes(size, "little")
        if resolved.startswith("["):
            if initial.startswith('c"') and initial.endswith('"'):
                raw = initial[2:-1]
                data, index = bytearray(), 0
                while index < len(raw):
                    if raw[index] == "\\":
                        data.append(int(raw[index + 1:index + 3], 16))
                        index += 3
                    else:
                        data.append(ord(raw[index]))
                        index += 1
                result = bytes(data)
            else:
                result = b"".join(self.initializer(*typed(item)) for item in split(initial[1:-1]))
        elif fields := self.members(ty):
            result = b""
            for field, item in zip(fields, split(initial[1:-1]), strict=True):
                _, boundary = self.layout(field)
                result = result.ljust(align(len(result), boundary), b"\0") + self.initializer(field, typed(item)[1])
            result = result.ljust(size, b"\0")
        else:
            raise Unsupported("unsupported initializer: " + initial)
        if len(result) != size:
            raise Unsupported("initializer size mismatch")
        return result

    def assembly(self):
        result = ["; Experimental Clang IR lowering, MICA32, scalar ABI subset.", ".arch mica32v2"]
        defined = {f[0] for f in self.functions}
        result += [".extern " + name for name in self.external if name not in defined]
        for name, returns, args, body in self.functions:
            result += Function(self, name, returns, args, body).assembly()
        for name, ty, initial, boundary in self.globals:
            data = self.initializer(ty, initial)
            result += [f".align {boundary}", ".global " + name, name + ":"]
            for offset in range(0, len(data), 32):
                result.append(".byte " + ",".join(map(str, data[offset:offset + 32])))
        return "\n".join(result) + "\n"


class Function:
    def __init__(self, module, name, returns, args, body):
        self.module, self.name, self.returns, self.args, self.body = module, name, returns, args, body
        if len(args) > 4:
            raise Unsupported(name + ": at most four scalar arguments")
        self.slots, self.objects, self.code, self.serial = {}, {}, [], 0
        offset = 8  # saved x5 and link register, within an aligned frame
        for arg in args:
            ty, _ = typed(arg)
            if ty not in ("ptr", "i8", "i16", "i32"):
                raise Unsupported("aggregate argument")
            self.slots[value(arg)] = offset
            offset += 4
        for line in body:
            if match := re.match(r"(%[\w.]+) = (.+)", line):
                dest, op = match.groups()
                if op.startswith("alloca "):
                    ty, rest = typed(op[7:])
                    if not re.fullmatch(r", align (1|2|4|8|16)", rest):
                        raise Unsupported("dynamic or extended alloca: " + line)
                    size, boundary = module.layout(ty)
                    boundary = max(boundary, int(rest.split()[-1]))
                    # SP is aligned to 16; larger explicit alignments are rejected.
                    offset = align(offset, boundary)
                    self.objects[dest] = offset
                    offset += size
                else:
                    self.slots[dest] = offset
                    offset += 4
        self.frame = align(offset, 16)
        if self.frame > 8000:
            raise Unsupported(name + ": stack frame exceeds 8000 bytes")

    def emit(self, *lines):
        self.code.extend(lines)

    def label(self, name):
        return self.name + "." + name.lstrip("%")

    def unique(self):
        self.serial += 1
        return self.label("cc" + str(self.serial))

    def load(self, val, reg):
        if val in self.objects:
            self.emit(f"add3i x{reg},sp,{self.objects[val]}")
        elif val in self.slots:
            self.emit(f"add3i x5,sp,{self.slots[val]}", f"ldw x{reg},[x5]")
        elif val.startswith("@"):
            self.emit(f"li32 x{reg},{val[1:]}")
        elif val in ("false", "null", "true"):
            self.emit(f"li8 x{reg},{int(val == 'true')}")
        elif re.fullmatch(r"-?\d+", val):
            self.emit(f"li32 x{reg},{int(val) & 0xffffffff}")
        else:
            raise Unsupported("undefined or unsupported value: " + val)

    def save(self, dest, reg=1, ty="i32"):
        if ty in ("i1", "i8", "i16"):
            bits = int(ty[1:])
            self.emit(f"shl3i x{reg},x{reg},{32 - bits}", f"shr3i x{reg},x{reg},{32 - bits}")
        self.emit(f"add3i x5,sp,{self.slots[dest]}", f"stw x{reg},[x5]")

    def gep(self, text, dest):
        args = split(text.removeprefix("inbounds ").removeprefix("nuw "))
        ty = args[0]
        self.load(value(args[1]), 1)
        for index, item in enumerate(args[2:]):
            val = value(item)
            fields = self.module.members(ty)
            if index and fields:
                field = int(val)
                if not 0 <= field < len(fields):
                    raise Unsupported("struct index out of range")
                offset = 0
                for previous in fields[:field]:
                    n, a = self.module.layout(previous)
                    offset = align(offset, a) + n
                offset = align(offset, self.module.layout(fields[field])[1])
                self.emit(f"add3i x1,x1,{offset}")
                ty = fields[field]
                continue
            if index:
                match = re.fullmatch(r"\[\d+ x (.+)\]", self.module.resolve(ty))
                if not match:
                    raise Unsupported("unsupported GEP descent: " + ty)
                ty = match[1]
            size, _ = self.module.layout(ty)
            if re.fullmatch(r"-?\d+", val):
                self.load(str((int(val) * size) & 0xffffffff), 2)
            else:
                self.load(val, 2)
                if size & (size - 1):
                    raise Unsupported("dynamic GEP requires power-of-two element size")
                if size > 1:
                    self.emit(f"shl3i x2,x2,{size.bit_length() - 1}")
            self.emit("add x1,x2")
        self.save(dest)

    def instruction(self, line):
        if line.endswith(":"):
            self.emit(self.label(line[:-1]) + ":")
            return
        dest, op = (line.split(" = ", 1) if " = " in line else (None, line))
        if op.startswith("alloca "):
            return
        if op.startswith("ret "):
            if op != "ret void":
                self.load(value(op[4:]), 1)
            self.emit("j " + self.label("epilogue"))
        elif op.startswith("br label "):
            self.emit("j " + self.label(op[9:]))
        elif op.startswith("br i1 "):
            cond, yes, no = split(op[3:])
            self.load(value(cond), 1)
            fall = self.unique()
            self.emit(f"bz x1,{fall}", "j " + self.label(yes.removeprefix("label ")),
                      fall + ":", "j " + self.label(no.removeprefix("label ")))
        elif op.startswith("store "):
            args = split(op[6:].removeprefix("volatile "))
            ty, _ = typed(args[0])
            mnemonic = {"i1": "stb", "i8": "stb", "i16": "sth", "i32": "stw", "ptr": "stw"}.get(ty)
            if not mnemonic:
                raise Unsupported("unsupported store type " + ty)
            self.load(value(args[0]), 1)
            self.load(value(args[1]), 2)
            self.emit(f"{mnemonic} x1,[x2]")
        elif op.startswith("load "):
            args = split(op[5:].removeprefix("volatile "))
            mnemonic = {"i1": "ldbu", "i8": "ldbu", "i16": "ldhu", "i32": "ldw", "ptr": "ldw"}.get(args[0])
            if not mnemonic:
                raise Unsupported("unsupported load type " + args[0])
            self.load(value(args[1]), 2)
            self.emit(f"{mnemonic} x1,[x2]")
            self.save(dest, ty=args[0])
        elif op.startswith("getelementptr "):
            self.gep(op[14:], dest)
        elif match := re.fullmatch(r"(sext|zext|trunc|ptrtoint|inttoptr) (.+) to (\w+)", op):
            cast, arg, target = match.groups()
            ty, _ = typed(arg)
            self.load(value(arg), 1)
            if cast == "sext" and ty != "i32":
                bits = int(ty[1:])
                self.emit(f"shl3i x1,x1,{32 - bits}", f"sar3i x1,x1,{32 - bits}")
            elif cast == "zext" and ty != "i32":
                bits = int(ty[1:])
                self.emit(f"shl3i x1,x1,{32 - bits}", f"shr3i x1,x1,{32 - bits}")
            if target not in ("i1", "i8", "i16", "i32", "ptr"):
                raise Unsupported("unsupported cast destination " + target)
            self.save(dest, ty=target)
        elif match := re.fullmatch(r"icmp (eq|ne|slt|sle|sgt|sge|ult|ule|ugt|uge) (.+)", op):
            predicate, operands = match.groups()
            left, right = split(operands)
            ty, _ = typed(left)
            self.load(value(left), 1)
            self.load(right, 2)
            if ty in ("i8", "i16"):
                for reg in (1, 2):
                    right_shift = "sar3i" if predicate.startswith("s") else "shr3i"
                    self.emit(f"shl3i x{reg},x{reg},{32 - int(ty[1:])}", f"{right_shift} x{reg},x{reg},{32 - int(ty[1:])}")
            reverse = predicate.endswith(("gt", "le"))
            mnemonic = "seq3" if predicate in ("eq", "ne") else "slt3" if predicate.startswith("s") else "sltu3"
            self.emit(f"{mnemonic} x3,x{2 if reverse else 1},x{1 if reverse else 2}")
            if predicate == "ne" or predicate.endswith(("ge", "le")):
                self.emit("xor3i x3,x3,1")
            self.save(dest, 3)
        elif match := re.fullmatch(r"(add|sub|mul|and|or|xor|shl|lshr|ashr) (?:(?:nuw|nsw) )*(i1|i8|i16|i32) (.+)", op):
            operation, ty, operands = match.groups()
            left, right = split(operands)
            self.load(left, 1)
            self.load(right, 2)
            if operation == "ashr" and ty != "i32":
                bits = int(ty[1:])
                self.emit(f"shl3i x1,x1,{32 - bits}", f"sar3i x1,x1,{32 - bits}")
            if operation == "mul" and not self.module.multiply:
                loop, skip, done = self.unique(), self.unique(), self.unique()
                self.emit("li8 x3,0", f"bz x2,{done}", loop + ":", "and3i x4,x2,1",
                          f"bz x4,{skip}", "add x3,x1", skip + ":", "shli x1,1", "shri x2,1",
                          f"bnz x2,{loop}", done + ":", "mov x1,x3")
            else:
                mnemonic = {"lshr": "shr", "ashr": "sar"}.get(operation, operation)
                self.emit(f"{mnemonic}3 x1,x1,x2")
            self.save(dest, ty=ty)
        elif op.startswith("call "):
            match = re.fullmatch(r"call (?:\w+ )*(void|i8|i16|i32|ptr) @([\w.]+)\((.*)\)(?: #[0-9]+)?", op)
            if not match or match[2].startswith("llvm."):
                raise Unsupported("unsupported call/intrinsic: " + op)
            returns, name, operands = match.groups()
            args = split(operands) if operands else []
            if len(args) > 4:
                raise Unsupported("at most four scalar call arguments")
            for index, arg in enumerate(args):
                self.load(value(arg), index + 1)
            self.emit("call " + name)
            if dest:
                self.save(dest, ty=returns)
        else:
            raise Unsupported("unsupported instruction: " + line)

    def assembly(self):
        self.emit(".global " + self.name, self.name + ":", f"add3i sp,sp,-{self.frame}",
                  "stw x5,[sp]", "stw x6,[sp+4]")
        for index, arg in enumerate(self.args):
            self.save(value(arg), index + 1, typed(arg)[0])
        for line in self.body:
            try:
                self.instruction(line)
            except (ValueError, KeyError) as error:
                raise Unsupported(f"{self.name}: {line}: {error}") from error
        self.emit(self.label("epilogue") + ":", "ldw x5,[sp]", "ldw x6,[sp+4]",
                  f"add3i sp,sp,{self.frame}", "ret")
        return self.code
