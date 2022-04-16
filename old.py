# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org>

def get_old_symbols_by_ram(lines: Iterable[str]):

    symbol_def = re.compile(r"([a-zA-Z_][0-9a-zA-Z_]*)\s*=\s*(0x[0-9a-fA-F]+)\s*;")

    symbols_by_ram = dict()

    for line in lines:
        line = line.strip()
        if line == "":
            continue
        if line.startswith("/*") and line.endswith("*/"):
            if "*/" in line[:-1]:
                raise Exception('"Complex" comments not handled 1', line)
            continue
        if line.endswith("*/"):
            comment_start = line.find("/*")
            if comment_start < 0:
                raise Exception('"Complex" comments not handled 2 (multiline?)', line)
            if line[:-1].find("*/", comment_start + 1) >= 0:
                raise Exception('"Complex" comments not handled 3', line)
            line = line[:comment_start]
            line = line.strip()
        m = symbol_def.fullmatch(line)
        if m is None:
            raise Exception("line does not match a symbol definition", line)
        symbol = m[1]
        ram_str = m[2]
        ram = int(ram_str, 16)
        if ram in symbols_by_ram:
            if (
                symbols_by_ram[ram] == symbol
            ):  # ignore duplicate but identical definitions
                pass
            # memset and fabsf are defined manually as a hacky fix,
            # they don't actually appear in the decomp map file
            elif {symbol, symbols_by_ram[ram]} == {"Lib_MemSet", "memset"}:
                symbols_by_ram[ram] = "Lib_MemSet"
            elif {symbol, symbols_by_ram[ram]} == {"absf", "fabsf"}:
                symbols_by_ram[ram] = "absf"
            else:
                raise Exception(
                    "Duplicate symbol for address", ram, symbols_by_ram[ram], symbol
                )
        else:
            symbols_by_ram[ram] = symbol
    return symbols_by_ram

def compare():
    # read old symbols
    with open("oot_mq_debug/syms.ld") as f:
        lines = f.readlines()
    old_symbols_by_ram = get_old_symbols_by_ram(lines)


    symbol_new = []
    symbol_changes = dict()
    symbol_removed = set(old_symbols_by_ram.values())

    for objfile, objfile_symbols in new_symbols.items():
        for section in (".text", ".data", ".rodata", ".bss"):
            section_symbols = objfile_symbols.get(section)
            if section_symbols:
                for symbol, (ram, rom) in section_symbols.items():
                    old_symbol = old_symbols_by_ram.get(ram)
                    if old_symbol is None:
                        symbol_new.append(symbol)
                    elif symbol != old_symbol:
                        if old_symbol in symbol_changes:
                            raise Exception(
                                "Duplicate new symbol",
                                old_symbol,
                                symbol_changes[old_symbol],
                                symbol,
                            )
                        symbol_changes[old_symbol] = symbol
                    if old_symbol is not None:
                        if old_symbol not in symbol_removed:
                            if (
                                old_symbol == "MapMark_Draw"
                            ):  # /!\ issue in current syms.ld
                                pass
                            else:
                                raise Exception(
                                    "Something is duplicate about", old_symbol
                                )
                        else:
                            symbol_removed.remove(old_symbol)

    if len(symbol_new) != len(set(symbol_new)):
        raise Exception("Duplicate new symbols")

    # write changes
    # + symbol is a new symbol
    # - symbol is a removed symbol
    # symA -> symB is a renamed symbol
    with open("changes.txt", "w") as f:
        for symbol in symbol_new:
            f.write(f"+ {symbol}\n")
        for old_symbol, new_symbol in symbol_changes.items():
            f.write(f"{old_symbol} -> {new_symbol}\n")
        for symbol in symbol_removed:
            f.write(f"- {symbol}\n")
