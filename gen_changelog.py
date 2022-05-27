#!/bin/env python3

# SPDX-License-Identifier: CC0-1.0 OR Unlicense

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument(
    "old_syms_json_path",
    help="Path to .json with old symbols",
    type=Path,
)
parser.add_argument(
    "new_syms_json_path",
    help="Path to .json with new symbols",
    type=Path,
)
parser.add_argument(
    "output_dir_path",
    help="Path to directory to write output files into",
    type=Path,
)
args = parser.parse_args()

with open(args.old_syms_json_path) as f:
    old_syms = json.load(f)
assert isinstance(old_syms, dict)

with open(args.new_syms_json_path) as f:
    new_syms = json.load(f)
assert isinstance(new_syms, dict)

# find differences
changes = dict()

new_o_files = new_syms.keys() - old_syms.keys()
removed_o_files = old_syms.keys() - new_syms.keys()
common_files = old_syms.keys() & new_syms.keys()

# TODO handle file renames
changes["files"] = {
    "new": list(new_o_files),
    "removed": list(removed_o_files),
}

consider_if_used = True
changed_syms = dict()
changes["symbols"] = changed_syms

for o_file in common_files:
    old_syms_by_section = old_syms[o_file]
    assert isinstance(old_syms_by_section, dict)
    new_syms_by_section = new_syms[o_file]
    assert isinstance(new_syms_by_section, dict)

    if old_syms_by_section == new_syms_by_section:
        continue

    file_changed_syms = dict()
    changed_syms[o_file] = file_changed_syms

    if new_syms_by_section.keys() != old_syms_by_section.keys():
        file_changed_syms["sections"] = {
            "new": list(new_syms_by_section.keys() - old_syms_by_section.keys()),
            "removed": list(old_syms_by_section.keys() - new_syms_by_section.keys()),
        }

    for section in new_syms_by_section.keys() & old_syms_by_section.keys():
        old_syms_syms = old_syms_by_section[section]
        assert isinstance(old_syms_syms, dict)
        new_syms_syms = new_syms_by_section[section]
        assert isinstance(new_syms_syms, dict)
        if old_syms_syms == new_syms_syms:
            continue

        if new_syms_syms.keys() != old_syms_syms.keys():
            new_syms_names = list(new_syms_syms.keys() - old_syms_syms.keys())
            if consider_if_used:
                new_syms_names = [v for v in new_syms_names if new_syms_syms[v]["used"]]
            removed_syms_names = list(old_syms_syms.keys() - new_syms_syms.keys())
            if consider_if_used:
                removed_syms_names = [
                    v for v in removed_syms_names if old_syms_syms[v]["used"]
                ]
            renamed_syms_names = dict()

            for removed_sym_name in removed_syms_names.copy():
                removed_sym_name_info = old_syms_syms[removed_sym_name]
                if consider_if_used and not removed_sym_name_info["used"]:
                    continue
                if removed_sym_name_info["ram"] is not None:
                    comp_info_key = "ram"
                else:
                    assert removed_sym_name_info["rom"] is not None, (
                        "symbol "
                        + removed_sym_name
                        + " in "
                        + o_file
                        + " has neither ram nor rom in old syms .json..."
                    )
                    comp_info_key = "rom"
                found_new_candidate = False
                for (
                    new_sym_name_candidate,
                    new_sym_name_candidate_info,
                ) in new_syms_syms.items():
                    if consider_if_used and not new_sym_name_candidate_info["used"]:
                        continue
                    if (
                        removed_sym_name_info[comp_info_key]
                        == new_sym_name_candidate_info[comp_info_key]
                    ):
                        if found_new_candidate:
                            print(
                                "Found other new candidate symbol for renaming",
                                removed_sym_name,
                            )
                            if isinstance(renamed_syms_names[removed_sym_name], str):
                                renamed_syms_names[removed_sym_name] = [
                                    renamed_syms_names[removed_sym_name]
                                ]
                            renamed_syms_names[removed_sym_name].append(
                                removed_sym_name
                            )
                            continue
                        found_new_candidate = True
                        renamed_syms_names[removed_sym_name] = new_sym_name_candidate
                        removed_syms_names.remove(removed_sym_name)
                        try:
                            new_syms_names.remove(new_sym_name_candidate)
                        except ValueError:  # not in list
                            print(
                                "Found that old symbol",
                                removed_sym_name,
                                removed_sym_name_info,
                            )
                            print(
                                "was renamed to",
                                new_sym_name_candidate,
                                new_sym_name_candidate_info,
                            )
                            print(
                                "But",
                                new_sym_name_candidate,
                                "already was a symbol? not in the new syms list",
                            )
                            print("Or other old symbols already map to this symbol:")
                            print(
                                [
                                    from_sym
                                    for from_sym, to_sym in renamed_syms_names.items()
                                    if to_sym == new_sym_name_candidate
                                ]
                            )
                            print("Continuing...")

            file_changed_syms[section] = {
                "new": new_syms_names,
                "removed": removed_syms_names,
                "renamed": renamed_syms_names,
            }


print(changes)

if not args.output_dir_path.exists():
    args.output_dir_path.mkdir()

with open(args.output_dir_path / "changelog.json", "w") as f:
    json.dump(changes, f)

with open(args.output_dir_path / "changelog.md", "w") as f:
    f.write("# Files\n")
    f.write("## New Files\n")
    f.writelines(f"- `{o_file}`\n" for o_file in changes["files"]["new"])
    f.write("## Removed Files\n")
    f.writelines(f"- `{o_file}`\n" for o_file in changes["files"]["removed"])
    f.write("# Symbols\n")
    for o_file, changes_by_section in changes["symbols"].items():
        if not any(
            any(changes_in_section.values())
            for changes_in_section in changes_by_section.values()
        ):
            continue
        f.write(f"## `{o_file}`\n")
        for section, changes_in_section in changes_by_section.items():
            if not any(changes_in_section.values()):
                continue
            f.write(f"### `{section}`\n")
            if changes_in_section.get("new"):
                f.write(f"#### Added\n")
                f.writelines(
                    f"- `{change_new_elem}`\n"
                    for change_new_elem in changes_in_section["new"]
                )
            if changes_in_section.get("removed"):
                f.write(f"#### Removed\n")
                f.writelines(
                    f"- `{change_new_elem}`\n"
                    for change_new_elem in changes_in_section["removed"]
                )
            if changes_in_section.get("renamed"):
                f.write(f"#### Renamed\n")
                f.writelines(
                    f"- `{change_from}` -> `{change_to}`\n"
                    if isinstance(change_to, str)
                    else (
                        f"- `{change_from}` -> ? "
                        + ", ".join(
                            f"`{change_to_elem}`" for change_to_elem in change_to
                        )
                        + "\n"
                    )
                    for change_from, change_to in changes_in_section["renamed"].items()
                )

with open(args.output_dir_path / "changelog.txt", "w") as f:
    f.write("Files\n")
    f.writelines(f" +{o_file}\n" for o_file in changes["files"]["new"])
    f.writelines(f" -{o_file}\n" for o_file in changes["files"]["removed"])
    f.write("\n")
    f.write("Symbols\n")
    for o_file, changes_by_section in changes["symbols"].items():
        if not any(
            any(changes_in_section.values())
            for changes_in_section in changes_by_section.values()
        ):
            continue
        f.write(f" {o_file}\n")
        for section, changes_in_section in changes_by_section.items():
            if not any(changes_in_section.values()):
                continue
            f.write(f"  {section}\n")
            if changes_in_section.get("new"):
                f.writelines(
                    f"   +{change_new_elem}\n"
                    for change_new_elem in changes_in_section["new"]
                )
            if changes_in_section.get("removed"):
                f.writelines(
                    f"   -{change_new_elem}\n"
                    for change_new_elem in changes_in_section["removed"]
                )
            if changes_in_section.get("renamed"):
                f.writelines(
                    f"   {change_from} -> {change_to}\n"
                    if isinstance(change_to, str)
                    else (
                        f"   {change_from} -> ? "
                        + ", ".join(
                            f"{change_to_elem}" for change_to_elem in change_to
                        )
                        + "\n"
                    )
                    for change_from, change_to in changes_in_section["renamed"].items()
                )
