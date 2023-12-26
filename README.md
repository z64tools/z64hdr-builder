This tool was supplanted by https://github.com/z64tools/z64genhdr

# z64hdr-builder

Stuff to make updating z64hdr easy

z64hdr: https://github.com/z64tools/z64hdr

Usage: run `upgrade_assist.py` with what it needs and follow instructions

## upgrade_assist.py

A script for running commands to update z64hdr. For "linux", probably doesn't work in windows as is

Prerequisites:
- have a clone/copy of current z64hdr somewhere (it will be modified!)
- have an OK build of the decomp repo

Example usage:

```
./upgrade_assist.py ~/Documents/oot/ oot_mq_debug ~/Documents/z64hdr
```

(`oot_mq_debug` being the version decomp is built Ok for and corresponding to the folder in z64hdr)

Press enter or what's needed to confirm running commands.

Some changes are done on top of decomp's headers, with a patch. if they don't apply cleanly, fix the conflicts and say yes to remaking the patch file (it will overwrite the current patch file, when stuff works don't forget to git add commit push the patch to z64hdr-builder)

changelog will be written to the z64hdr-builder/changelogs/ folder

The z64hdr repo will be modified all it needs and is ready to git add commit push

## decomp_getter.py

It is called by upgrade_assist.py

It copies headers from decomp, and parses the map file into syms.json (example https://github.com/Dragorn421/z64hdr/blob/b7ebb52e98f86487947f4dde189b5261e7499b6f/oot_mq_debug/syms.json ) and linker scripts (example https://github.com/Dragorn421/z64hdr/blob/b7ebb52e98f86487947f4dde189b5261e7499b6f/oot_mq_debug/syms_src.ld )

## gen_changelog.py

It is called by upgrade_assist.py

Generates changelog in json, markdown and txt format from two syms.json files (like https://github.com/Dragorn421/z64hdr/blob/b7ebb52e98f86487947f4dde189b5261e7499b6f/oot_mq_debug/syms.json )

Example output (based on z64hdr at https://github.com/Dragorn421/z64hdr/tree/b7ebb52e98f86487947f4dde189b5261e7499b6f and decomp at https://github.com/zeldaret/oot/tree/e68f321777be140726591b9a5dc4c45fe127d6d3 ): https://gist.github.com/Dragorn421/6988a192e8876ffb08a25843fa7785f6

Example usage:

```
./gen_changelog.py /home/dragorn421/Documents/z64hdr/oot_mq_debug/syms.json syms_oot_mq_debug/syms.json ./changelog/
```

## LICENSE

Either CC0 or Unlicense, your choice. (public domain)

`# SPDX-License-Identifier: CC0-1.0 OR Unlicense`

This readme's contents is also public domain (cc0 or unlicense, your choice)
