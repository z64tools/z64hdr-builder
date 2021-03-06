#!/bin/env python3

# SPDX-License-Identifier: CC0-1.0 OR Unlicense

import argparse
import subprocess
import os.path

from typing import List


def confirm_call(cmd_args: List[str], stdin=None, stdout=None, check=True):
    print("Command:")
    if any(any(c.isspace() for c in arg) for arg in cmd_args):
        print(cmd_args)
    else:
        print(" ".join(cmd_args))
    input("Press enter to run")
    kwargs = dict()
    if stdin is not None:
        kwargs["stdin"] = stdin
    if stdout is not None:
        kwargs["stdout"] = stdout
    return subprocess.run(cmd_args, check=check, **kwargs)


parser = argparse.ArgumentParser()
parser.add_argument("oot_decomp_repo_path", help="Path to oot decomp")
parser.add_argument("oot_version", help="OoT version (oot_mq_debug)")
parser.add_argument("z64hdr_repo_path", help="Path to z64hdr repo")
args = parser.parse_args()

syms_oot_version_path = f"syms_{args.oot_version}"
z64hdr_include_path = args.z64hdr_repo_path + os.path.sep + "include"
z64hdr_oot_version_path = args.z64hdr_repo_path + os.path.sep + args.oot_version

print("--- Get headers and symbols from decomp")
confirm_call(
    [
        "./decomp_getter.py",
        args.oot_decomp_repo_path,
        syms_oot_version_path,
        "include-base",
    ]
)

print("--- Copy include-base to include")
confirm_call(["rm", "-r", "include"])
confirm_call(["cp", "-r", "include-base", "include"])

print("--- Patch include (make sure to fix conflicts if any)")
with open("include-patch.txt") as f:
    patch_cp = confirm_call(["patch", "-p0"], stdin=f, check=False)
if patch_cp.returncode == 0:
    print("No conflicts")
elif patch_cp.returncode == 1:
    print("THERE ARE CONFLICTS!")
    print("Fix the conflicts")
    print("Also delete the .orig and .rej files")
    print("then generate a new patch to update it for the future")
else:
    print("patch failed unexpectedly (not due to conflicts)")

print("Fix any conflict, or make changes if needed, in include/")

if (
    input(
        "Generate new patch file? "
        "(for example if there was conflicts, or if more changes were made) "
        "('yes' for yes): "
    )
    == "yes"
):
    with open("include-patch.txt", "w") as f:
        p = confirm_call(
            ["diff", "-Naur", "include-base", "include"], stdout=f, check=False
        )
    if p.returncode == 0:
        print("include-base and include are the same!")
    elif p.returncode == 2:
        print("diff failed")

print("--- Changelog generation")

if input("Generate changelog? ('yes' for yes): ") == "yes":
    confirm_call(["rm", "-r", "./changelog/"])
    confirm_call(
        [
            "./gen_changelog.py",
            z64hdr_oot_version_path + os.path.sep + "syms.json",
            syms_oot_version_path + os.path.sep + "syms.json",
            "./changelog/",
        ]
    )

print("--- Update z64hdr repo")

confirm_call(["rm", "-r", z64hdr_include_path])
confirm_call(["cp", "-r", "include", z64hdr_include_path])

print(
    "Copy syms.ld, z64hdr.h and z64hdr.ld from z64hdr repo to builder's syms repo "
    "(all other files will be ignored and deleted)"
)
for file in ("syms.ld", "z64hdr.h", "z64hdr.ld"):
    confirm_call(
        [
            "cp",
            z64hdr_oot_version_path + os.path.sep + file,
            syms_oot_version_path + os.path.sep + file,
        ]
    )

confirm_call(["rm", "-r", z64hdr_oot_version_path])
confirm_call(["cp", "-r", syms_oot_version_path, z64hdr_oot_version_path])
