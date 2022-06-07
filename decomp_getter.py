#!/bin/env python3

# SPDX-License-Identifier: CC0-1.0 OR Unlicense

# The map parsing is based on this asm-differ fork
# https://github.com/Dragorn421/asm-differ/blob/bc4189857a2218f320cd81d88ba508915c9201c2/diff.py#L969
# asm-differ is also in the public domain (unlicense)

import argparse
from pathlib import Path
import shutil
import os
import re
import json

from typing import (
    Tuple,
    Dict,
    Iterable,
    Generator,
)


def parse_map_file(
    mapfile_lines: Iterable[str],
) -> Generator[Tuple[str, str, int, int, str], None, None]:

    symbol_pattern = re.compile(r"[a-zA-Z_][0-9a-zA-Z_]*")

    cur_section = None
    cur_objfile = None
    ram_to_rom = None

    for line in mapfile_lines:
        tokens = line.split()

        if not tokens:
            continue

        # hardcode some things that mess up the map parsing.
        # this map parsing doesn't need to be robust anyway
        if (
            tokens == ["Memory", "Configuration"]
            or tokens[0] == "LOAD"
            or tokens == ["OUTPUT(zelda_ocarina_mq_dbg.elf", "elf32-tradbigmips)"]
            or tokens == ["*(.debug_info", ".gnu.linkonce.wi.*)"]
        ):
            continue

        if tokens[0] in {".text", ".data", ".rodata", ".bss"}:
            cur_objfile = tokens[3]
            cur_section = tokens[0]
        elif line.startswith(" ."):
            cur_section = None

        if "load address" in line:
            if len(tokens) == 6:
                ram_str = tokens[1]
                rom_str = tokens[5]
            elif len(tokens) == 5:
                # long segment names are put in the previous line, shifting tokens by 1
                ram_str = tokens[0]
                rom_str = tokens[4]
            else:
                raise Exception(
                    f"Unexpected amount of tokens {len(tokens)} {tokens} in line {line}"
                )
            ram = int(ram_str, 0)
            rom = int(rom_str, 0)
            ram_to_rom = rom - ram

            # "load address" comes before sections
            cur_objfile = None
            cur_section = None

        if len(tokens) == 2:
            try:
                offset = int(tokens[0], 0)
            except ValueError:
                raise Exception(f"Could not parse {tokens}")
            if ram_to_rom is None:
                ram = None
                rom = offset
            else:
                ram = offset
                rom = ram + ram_to_rom
            symbol_name = tokens[1]
            if symbol_pattern.fullmatch(symbol_name):
                yield (
                    cur_objfile,
                    cur_section,
                    ram,
                    rom,
                    symbol_name,
                )
            else:
                if not symbol_name.startswith("0x"):
                    raise Exception(f"Could not parse {tokens}")


def read_and_organize_symbols(mapfile_lines):
    symbols: Dict[str, Dict[str, Dict[str, Tuple[int, int]]]] = dict()

    for objfile, section, ram, rom, symbol in parse_map_file(mapfile_lines):
        if objfile not in symbols:
            symbols[objfile] = dict()
        if section not in symbols[objfile]:
            symbols[objfile][section] = dict()
        if symbol in symbols[objfile][section]:
            raise Exception("Duplicate symbol", symbol)
        symbols[objfile][section][symbol] = (ram, rom)
        # print(objfile, section, ram, rom, symbol)
        if ram is None:
            if symbol not in {"entrypoint"}:
                raise Exception(
                    "the only expected symbol without a load address is entrypoint, encountered another one",
                    symbol,
                )
        else:
            pass

    return symbols


def update_z64hdr(
    oot_decomp_repo_path: Path,
    output_path_syms: Path,
    output_path_includes: Path,
):
    """
    `oot_decomp_repo_path` should be a `Path` to the oot decomp repo
        for example `Path("/home/dragorn421/Documents/oot/")`

    Writes syms_*.ld files under `output_path_syms`,
        and copies undefined_syms.txt there,
        and dumps the parsed symbols from the map to syms.json

    Copies .h files from decomp's assets, include and src into `output_path_includes`
    """

    for empty_dir_path in (output_path_syms, output_path_includes):
        if empty_dir_path.exists():
            while (
                input(
                    f"Delete directory {empty_dir_path.absolute()} ? 'yes' to confirm: "
                )
                != "yes"
            ):
                pass
            shutil.rmtree(empty_dir_path)

        empty_dir_path.mkdir(parents=True, exist_ok=True)

    # read map
    with (oot_decomp_repo_path / "build" / "z64.map").open() as f:
        mapfile_lines = f.readlines()
    new_symbols = read_and_organize_symbols(mapfile_lines)

    syms_dump = dict()

    # write new linker script

    # one out_lines_* per syms_*.ld file
    out_lines_src = []
    out_lines_assets_scenes = []
    out_lines_assets_objects = []
    out_lines_assets_others = []
    out_lines_others = []

    for objfile, objfile_symbols in new_symbols.items():
        # decide to which syms_*.ld file append this .o file's symbols
        out_lines = None
        skip = False
        if objfile.startswith("build/src/overlays/"):
            # we don't need the symbols from overlays
            # and because they get relocated using them usually makes little sense
            skip = True
        elif objfile.startswith("build/src/elf_message/"):
            # this is data which symbols aren't used directly
            skip = True
        elif (
            objfile == "build/asm/entry.o"
            # decomp 4775fd4a7ea8077f603900def093124f8aa7cec6 : asm/entry.s -> src/makerom/entry.s
            or objfile == "build/src/makerom/entry.o"
        ):
            # skip `entrypoint` symbol
            skip = True
        elif objfile.startswith("build/src/"):
            out_lines = out_lines_src
        elif objfile.startswith("build/assets/scenes/"):
            out_lines = out_lines_assets_scenes
        elif objfile.startswith("build/assets/objects/"):
            out_lines = out_lines_assets_objects
        elif objfile.startswith("build/assets/"):
            out_lines = out_lines_assets_others
        else:
            out_lines = out_lines_others

        syms_dump[objfile] = {
            section: {
                symbol: {
                    "ram": f"0x{ram:08X}" if ram is not None else None,
                    "rom": (
                        f"0x{rom:08X}"
                        if rom is not None and section != ".bss"
                        else None
                    ),
                    "used": not skip,
                }
                for symbol, (ram, rom) in section_symbols.items()
            }
            for section, section_symbols in objfile_symbols.items()
        }

        if skip:
            continue

        # append symbols
        out_lines.append(f"/* {objfile} */")
        for section in (".text", ".data", ".rodata", ".bss"):
            section_symbols = objfile_symbols.get(section)
            if section_symbols:
                out_lines.append(f" /* {section} */")
                symbol_pad = max(len(symbol) for symbol in section_symbols.keys())
                for symbol, (ram, rom) in section_symbols.items():
                    try:
                        line = f"  {symbol:<{symbol_pad}} = 0x{ram:08X};"
                        if section != ".bss":
                            line += f"  /* ROM: 0x{rom:08X} */"
                    except:
                        print(
                            "Couldn't format line",
                            repr(symbol),
                            repr(ram),
                            repr(rom),
                            repr(symbol_pad),
                            repr(section),
                            repr(objfile),
                        )
                        raise
                    out_lines.append(line)
        out_lines.append("")

    with (output_path_syms / "syms.json").open("w") as f:
        json.dump(syms_dump, f, indent=1)

    # write syms_*.ld files

    for out_file_name, out_lines in (
        ("src", out_lines_src),
        ("assets_scenes", out_lines_assets_scenes),
        ("assets_objects", out_lines_assets_objects),
        ("assets_others", out_lines_assets_others),
        ("others", out_lines_others),
    ):
        with (output_path_syms / f"syms_{out_file_name}.ld").open("w") as f:
            f.writelines(f"{line}\n" for line in out_lines)

    with (oot_decomp_repo_path / "undefined_syms.txt").open() as f:
        undefined_syms = f.read()

    # convert single-line comments like `// abc` to `/* abc */`
    # (I think linker scripts can only have the multiline style comments)
    undefined_syms = re.sub(r"//([^\n]*)\n", "/*\\1 */\n", undefined_syms)

    with (output_path_syms / "undefined_syms.txt").open("w") as f:
        f.write(undefined_syms)

    # copy headers

    def copytree_ignore_onlycopyheaders(dir, entries: Iterable[str]):
        ignored_entries = []
        dirpath = Path(dir)
        for entry in entries:
            path = dirpath / entry
            if not (path.is_dir() or entry.endswith(".h")):
                ignored_entries.append(entry)
        return ignored_entries

    for folder in ("assets", "include", "src"):
        shutil.copytree(
            oot_decomp_repo_path / folder,
            output_path_includes / folder,
            ignore=copytree_ignore_onlycopyheaders,
        )
        cont = True
        while cont:
            empty_dirs = []
            for dirpath, dirnames, filenames in os.walk(output_path_includes / folder):
                if len(dirnames) == 0 and len(filenames) == 0:
                    empty_dirs.append(dirpath)
            cont = len(empty_dirs) != 0
            for empty_dir in empty_dirs:
                os.rmdir(empty_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oot_decomp_repo_path")
    parser.add_argument("output_path_syms")
    parser.add_argument("output_path_includes")
    args = parser.parse_args()
    update_z64hdr(
        oot_decomp_repo_path=Path(args.oot_decomp_repo_path),
        output_path_syms=Path(args.output_path_syms),
        output_path_includes=Path(args.output_path_includes),
    )


if __name__ == "__main__":
    main()
