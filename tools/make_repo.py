#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_repo.py — build the APT index plus Sileo/Zebra depictions for root-site.

Usage (from root-site):
    python tools/make_repo.py
    python tools/make_repo.py --check
    python tools/make_repo.py --dir . --meta repo-meta.json

The generator never touches the .debs. It reads each deb's control, overrides
only presentation fields from repo-meta.json, and keeps Package/Version/
Architecture/Depends/Conflicts/Replaces exactly as the deb declares.
"""

import argparse
import gzip
import hashlib
import html
import io
import json
import lzma
import os
import re
import shutil
import struct
import sys
import tarfile
import time

# ---------------------------------------------------------------- .deb parsing


def _iter_ar_members(fp):
    magic = fp.read(8)
    if magic != b"!<arch>\n":
        raise ValueError("not an ar archive")
    while True:
        hdr = fp.read(60)
        if len(hdr) < 60:
            return
        name = hdr[0:16].decode("ascii", "replace").strip()
        size = int(hdr[48:58].decode("ascii").strip())
        data = fp.read(size)
        if size % 2:
            fp.read(1)
        yield name, data


def read_control(deb_path):
    with open(deb_path, "rb") as fp:
        for name, data in _iter_ar_members(fp):
            if name.startswith("control.tar"):
                if name.endswith(".gz"):
                    raw = gzip.decompress(data)
                elif name.endswith(".xz") or name.endswith(".lzma"):
                    raw = lzma.decompress(data)
                elif name.endswith(".zst"):
                    import zstandard
                    raw = zstandard.ZstdDecompressor().decompress(data)
                else:
                    raw = data
                with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
                    for m in tar.getmembers():
                        base = os.path.basename(m.name)
                        if base == "control":
                            f = tar.extractfile(m)
                            if f:
                                return f.read().decode("utf-8", "replace")
    raise ValueError("control not found in %s" % deb_path)


def parse_control(text):
    """Return [(key, [value_line, continuation...]), ...] preserving order."""
    fields = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t":
            if not fields:
                raise ValueError("control continuation without a field")
            fields[-1][1].append(line)
        else:
            key, val = line.split(":", 1)
            fields.append([key, [val.lstrip()]])
    return fields


def render_control(fields):
    out = []
    for key, values in fields:
        out.append("%s: %s" % (key, values[0]))
        for cont in values[1:]:
            out.append(cont if cont[:1] in (" ", "\t") else " " + cont)
    return "\n".join(out) + "\n"


def get_field(fields, key, default=""):
    for k, values in fields:
        if k == key:
            return "\n".join(values)
    return default


def set_field(fields, key, value):
    values = value.split("\n")
    values = [values[0]] + [(v if v[:1] in (" ", "\t") else " " + v) for v in values[1:]]
    for item in fields:
        if item[0] == key:
            item[1] = values
            return
    fields.append([key, values])


def drop_fields(fields, keys):
    keys = set(keys)
    return [item for item in fields if item[0] not in keys]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def natural_key(value):
    return [int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", value or "")]


def version_key(version):
    """Small dpkg-like key: epoch, upstream, revision, with natural numbers."""
    epoch, sep, rest = version.partition(":")
    if not sep:
        epoch, rest = "0", version
    upstream, sep, revision = rest.rpartition("-")
    if not sep:
        upstream, revision = rest, ""
    try:
        epoch_num = int(epoch)
    except ValueError:
        epoch_num = 0
    return (epoch_num, natural_key(upstream), natural_key(revision))


# ---------------------------------------------------------------- model


class Deb(object):
    def __init__(self, path, filename):
        self.path = path
        self.filename = filename
        self.control_text = read_control(path)
        self.fields = parse_control(self.control_text)
        self.package = get_field(self.fields, "Package")
        self.version = get_field(self.fields, "Version")
        self.arch = get_field(self.fields, "Architecture")
        self.size = os.path.getsize(path)
        self.sha256 = sha256_of(path)
        self.md5 = md5_of(path)

    @property
    def key(self):
        return (self.package, self.version, self.arch)


class Meta(object):
    def __init__(self, data):
        self.data = data
        self.repo = data["repo"]
        self.packages = data["packages"]
        self.by_id = {}
        for package in self.packages:
            if package["package"] in self.by_id:
                raise ValueError("duplicate package metadata: %s" % package["package"])
            self.by_id[package["package"]] = package


def sort_variants(package):
    return sorted(package["variants"], key=lambda v: version_key(v["version"]), reverse=True)


def find_variant(package, version, arch):
    for variant in package["variants"]:
        if variant["version"] == version and variant.get("arch", "") == arch:
            return variant
    return None


# ---------------------------------------------------------------- depictions


def md_bullets(items):
    return "\n".join("- " + item for item in items)


def table_row(title, text):
    return {"class": "DepictionTableTextView", "title": title, "text": text}


def table_button(title, action):
    return {"class": "DepictionTableButtonView", "title": title,
            "action": action, "openExternal": True}


def subheader(title):
    return {"class": "DepictionSubheaderView", "title": title,
            "useBoldText": True, "useBottomMargin": True}


def markdown(text):
    return {"class": "DepictionMarkdownView", "markdown": text}


def variant_line(variant):
    return "%s · %s" % (variant["version"], variant["date"])


def build_sileo_depiction(package, repo, variants, deb_by_key):
    tabs = []

    # 1. Features
    feature_views = [markdown(md_bullets(package["features"]))]
    tabs.append({"class": "DepictionStackView", "tabname": "功能",
                 "views": feature_views})

    # 2. Compatibility
    compat_views = []
    for variant in variants:
        compat_views.append(subheader("v%s · %s" % (variant["version"], variant["arch"])))
        compat_views.append(table_row("机型", "、".join(variant.get("devices") or ["—"])))
        compat_views.append(table_row("验证 iOS", "、".join(variant.get("ios") or ["—"])))
        compat_views.append(table_row("越狱形态", variant.get("jailbreak", "—")))
        compat_views.append(table_row("验证状态", variant.get("verified", "—")))
    notes = package.get("compatibility", {}).get("notes") or []
    if notes:
        compat_views.append(subheader("注意事项"))
        compat_views.append(markdown(md_bullets(notes)))
    tabs.append({"class": "DepictionStackView", "tabname": "兼容性",
                 "views": compat_views})

    # 3. Changelog
    change_views = [markdown(
        "Sileo：安装后在插件页长按「修改 / MODIFY」选择历史版本；"
        "Irisin / Zebra 可直接在版本列表选择。每个版本下方有 .deb 直链。"
    )]
    for variant in variants:
        deb = deb_by_key.get((package["package"], variant["version"], variant["arch"]))
        change_views.append(subheader("v%s · %s" % (variant["version"], variant["date"])))
        change_views.append(table_row("验证", variant.get("verified", "—")))
        change_views.append(markdown(md_bullets(variant.get("changes") or ["—"])))
        if deb is not None:
            change_views.append(table_button(
                "下载 v%s（%s）" % (variant["version"], variant["arch"]),
                repo["url"].rstrip("/") + "/debs/" + deb.filename))
    for item in package.get("history") or []:
        change_views.append(subheader("v%s · %s" % (item.get("version", "—"),
                                                    item.get("date", "—"))))
        if item.get("status"):
            change_views.append(table_row("状态", item["status"]))
        change_views.append(markdown(md_bullets(item.get("notes") or ["—"])))
    tabs.append({"class": "DepictionStackView", "tabname": "更新日志",
                 "views": change_views})

    # 4. Feedback
    feedback_views = []
    feedback_views.append(markdown(
        "反馈时请附：插件版本、机型、iOS 版本、越狱环境、复现步骤、日志或截图。"
    ))
    if package.get("log_hint"):
        feedback_views.append(markdown(package["log_hint"]))
    feedback_views.append(table_button("项目仓库", package["repo_url"]))
    feedback_views.append(table_button("提交问题 / 反馈", repo["feedback_url"]))
    tabs.append({"class": "DepictionStackView", "tabname": "反馈",
                 "views": feedback_views})

    return {
        "minVersion": "0.4",
        "class": "DepictionTabView",
        "tintColor": repo.get("tint", "#3ea6ff"),
        "tabs": tabs,
    }


WEB_CSS = """
:root{--bg:#0b0d10;--card:#14181d;--line:#252b33;--text:#e8edf3;--muted:#93a1b1;--accent:#3ea6ff;--warn:#ffb454;--ok:#7ee0a8}
*{box-sizing:border-box}
body{margin:0;padding:34px 18px 64px;background:var(--bg);color:var(--text);
font:15px/1.7 -apple-system,"SF Pro Text","PingFang SC","Microsoft YaHei",sans-serif;-webkit-text-size-adjust:100%}
.wrap{max-width:760px;margin:0 auto}
a{color:var(--accent)}
.top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:18px}
.back{color:var(--muted);text-decoration:none;font-size:14px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.3px}
.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:16px}
.card h2{font-size:13px;margin:0 0 12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.tag{display:inline-block;font-size:12px;padding:3px 9px;border-radius:6px;border:1px solid var(--line);color:var(--muted)}
.tag.ok{color:var(--ok);border-color:#2c5a41}
.tag.warn{color:var(--warn);border-color:#5a4526}
.btn{display:inline-block;padding:9px 16px;border-radius:9px;background:var(--accent);color:#04121f;
font-weight:600;text-decoration:none;font-size:14px;margin:6px 8px 0 0}
.btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line)}
ul{margin:0;padding-left:20px}
li{margin-bottom:7px}
.note{color:var(--muted);font-size:14px}
.ver{border-top:1px solid var(--line);padding:16px 0}
.ver:first-of-type{border-top:0;padding-top:0}
.ver .head{font-weight:600;font-size:16px}
.ver .date{color:var(--muted);font-size:13px;margin-left:8px}
.ver .status{font-size:13px;color:var(--accent);margin-top:4px}
.ver ul{margin-top:8px;color:var(--muted)}
footer{color:#5f6b78;font-size:13px;margin-top:26px;text-align:center}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def render_web_page(package, repo, variants, deb_by_key):
    latest = variants[0]
    tags = []
    tags.append('<span class="tag">%s</span>' % esc(latest.get("arch", "")))
    tags.append('<span class="tag">%s</span>' % esc(latest.get("jailbreak", "")))
    verified = latest.get("verified", "")
    tag_class = "ok" if verified.startswith("已验证") else "warn"
    tags.append('<span class="tag %s">%s</span>' % (tag_class, esc(verified)))
    if len(variants) > 1:
        tags.append('<span class="tag">另有 %s</span>' %
                    esc(" / ".join(v["version"] for v in variants[1:])))

    feature_html = "<ul>%s</ul>" % "".join("<li>%s</li>" % esc(x) for x in package["features"])

    compat_html = []
    for variant in variants:
        compat_html.append(
            '<div class="ver"><div class="head">v%s</div>'
            '<div class="date">%s · %s</div>'
            '<div class="status">%s</div>'
            '<ul>'
            '<li>机型：%s</li><li>验证 iOS：%s</li><li>越狱形态：%s</li>'
            '</ul></div>' % (
                esc(variant["version"]), esc(variant["date"]), esc(variant["arch"]),
                esc(variant.get("verified", "—")),
                esc("、".join(variant.get("devices") or ["—"])),
                esc("、".join(variant.get("ios") or ["—"])),
                esc(variant.get("jailbreak", "—")),
            ))
    notes = package.get("compatibility", {}).get("notes") or []
    if notes:
        compat_html.append('<div class="note" style="margin-top:12px"><b>注意事项</b>'
                           '<ul>%s</ul></div>' %
                           "".join("<li>%s</li>" % esc(x) for x in notes))

    change_html = ['<p class="note">Sileo：安装后在插件页长按「修改 / MODIFY」选择历史版本；'
                   'Irisin / Zebra 可直接在版本列表选择。每个版本下方有 .deb 直链。</p>']
    for variant in variants:
        deb = deb_by_key.get((package["package"], variant["version"], variant["arch"]))
        change_html.append('<div class="ver"><div class="head">v%s</div>'
                           '<div class="date">%s · %s</div>'
                           '<div class="status">%s</div><ul>%s</ul>' % (
                               esc(variant["version"]), esc(variant["date"]),
                               esc(variant["arch"]), esc(variant.get("verified", "—")),
                               "".join("<li>%s</li>" % esc(x)
                                       for x in (variant.get("changes") or ["—"]))
                           ))
        if deb is not None:
            change_html.append('<a class="btn ghost" href="../../debs/%s">下载 v%s（%s）</a>' % (
                esc(deb.filename), esc(variant["version"]), esc(variant["arch"])))
        change_html.append("</div>")
    for item in package.get("history") or []:
        change_html.append('<div class="ver"><div class="head">v%s</div>'
                           '<div class="date">%s</div>'
                           '<div class="status">%s</div><ul>%s</ul></div>' % (
                               esc(item.get("version", "—")), esc(item.get("date", "—")),
                               esc(item.get("status", "")),
                               "".join("<li>%s</li>" % esc(x)
                                       for x in (item.get("notes") or ["—"]))
                           ))

    log_hint = ""
    if package.get("log_hint"):
        log_hint = '<p class="note">%s</p>' % esc(package["log_hint"])

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(name)s · %(repo_name)s</title><style>%(css)s</style></head>
<body><div class="wrap">
<div class="top"><a class="back" href="../../">← 返回 %(repo_name)s</a></div>
<h1>%(name)s</h1>
<p class="sub">%(summary)s</p>
<div class="tags">%(tags)s</div>

<div class="card" id="features"><h2>功能</h2>%(features)s</div>
<div class="card" id="compatibility"><h2>兼容性</h2>%(compat)s</div>
<div class="card" id="changelog"><h2>更新日志</h2>%(changelog)s</div>
<div class="card" id="feedback"><h2>反馈</h2>
<p>反馈时请附：插件版本、机型、iOS 版本、越狱环境、复现步骤、日志或截图。</p>
%(log_hint)s
<a class="btn" href="%(feedback_url)s">提交问题 / 反馈</a>
<a class="btn ghost" href="%(repo_url)s">项目仓库</a>
</div>
<footer>%(repo_name)s · <a href="%(repo_url)s">%(repo_url)s</a></footer>
</div></body></html>
""" % {
        "name": esc(package["display_name"]),
        "repo_name": esc(repo["name"]),
        "css": WEB_CSS,
        "summary": esc(package["summary"]),
        "tags": "".join(tags),
        "features": feature_html,
        "compat": "".join(compat_html),
        "changelog": "".join(change_html),
        "feedback_url": esc(repo["feedback_url"]),
        "repo_url": esc(package["repo_url"]),
        "log_hint": log_hint,
    }


def render_card(package, repo, variants):
    latest = variants[0]
    tags = ['<span class="tag">%s</span>' % esc(latest.get("arch", "")),
            '<span class="tag">%s</span>' % esc(latest.get("jailbreak", ""))]
    verified = latest.get("verified", "")
    tags.append('<span class="tag %s">%s</span>' %
                ("ok" if verified.startswith("已验证") else "warn", esc(verified)))
    if len(variants) > 1:
        tags.append('<span class="tag">另有 %s</span>' %
                    esc(" / ".join(v["version"] for v in variants[1:])))
    return """
    <div class="pkg">
      <div><span class="name">%s</span><span class="ver">%s</span></div>
      <div class="desc">%s</div>
      <div>%s</div>
      <div class="links">
        <a class="btn ghost" href="depictions/%s/index.html">详情</a>
        <a class="btn ghost" href="%s">项目仓库</a>
        <a class="btn ghost" href="%s">反馈</a>
      </div>
    </div>""" % (
        esc(package["display_name"]), esc(latest["version"]), esc(package["summary"]),
        "".join(tags), esc(package["package"]), esc(package["repo_url"]),
        esc(repo["feedback_url"]))


# ---------------------------------------------------------------- Packages


def build_packages(repo_dir, meta, debs, mapping):
    stanzas = []
    for package in meta.packages:
        variants = sort_variants(package)
        for variant in variants:
            deb = mapping[(package["package"], variant["version"], variant["arch"])]
            fields = parse_control(deb.control_text)
            fields = drop_fields(fields, ["Name", "Description", "Homepage",
                                         "SileoDepiction", "Depiction",
                                         "Filename", "Size", "SHA256", "MD5sum", "MD5Sum"])
            set_field(fields, "Name", package["display_name"])
            if not any(k == "Priority" for k, _ in fields):
                set_field(fields, "Priority", "optional")
            if not any(k == "Section" for k, _ in fields):
                set_field(fields, "Section", "Tweaks")

            verified = variant.get("verified", "—")
            devices = "、".join(variant.get("devices") or ["—"])
            ios = "、".join(variant.get("ios") or ["—"])
            if verified.startswith("未单独验证"):
                verify_line = "实机验证：未单独验证"
            elif verified.startswith("已验证"):
                verify_line = "实机验证：%s / iOS %s" % (devices, ios)
            else:
                verify_line = "实机验证：%s；%s / iOS %s" % (verified, devices, ios)
            desc = "%s\n %s\n 项目仓库：%s" % (
                package["summary"], verify_line, package["repo_url"])
            set_field(fields, "Description", desc)
            set_field(fields, "Homepage", package["repo_url"])
            set_field(fields, "SileoDepiction",
                      meta.repo["url"].rstrip("/") + "/sileodepictions/%s/index.json"
                      % package["package"])
            set_field(fields, "Depiction",
                      meta.repo["url"].rstrip("/") + "/depictions/%s/index.html"
                      % package["package"])
            fields.append(["Filename", ["debs/" + deb.filename]])
            fields.append(["Size", [str(deb.size)]])
            fields.append(["SHA256", [deb.sha256]])
            fields.append(["MD5sum", [deb.md5]])
            stanzas.append(render_control(fields).rstrip("\n"))
    return ("\n\n".join(stanzas) + "\n").encode("utf-8")


def write_release(repo_dir, packages_bytes, meta):
    variants = [("Packages", packages_bytes),
                ("Packages.gz", gzip.compress(packages_bytes, mtime=0)),
                ("Packages.xz", lzma.compress(packages_bytes, format=lzma.FORMAT_XZ))]
    for name, data in variants:
        with open(os.path.join(repo_dir, name), "wb") as fp:
            fp.write(data)
    md5_lines = [" %s %d %s" % (hashlib.md5(d).hexdigest(), len(d), n) for n, d in variants]
    sha_lines = [" %s %d %s" % (hashlib.sha256(d).hexdigest(), len(d), n) for n, d in variants]
    release = [
        "Origin: %s" % meta.repo["name"],
        "Label: %s" % meta.repo["name"],
        "Suite: stable",
        "Version: 1.0",
        "Codename: ios",
        "Architectures: iphoneos-arm64e iphoneos-arm64 iphoneos-arm",
        "Components: main",
        "Description: iOS 16–17 越狱插件源；每版标注实机验证状态",
        "Date: %s" % time.strftime("%a, %d %b %Y %H:%M:%S UTC", time.gmtime()),
        "MD5Sum:",
    ] + md5_lines + ["SHA256:"] + sha_lines + [""]
    with open(os.path.join(repo_dir, "Release"), "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(release))


# ---------------------------------------------------------------- landing page


def update_landing(repo_dir, meta, mapping):
    path = os.path.join(repo_dir, "index.html")
    text = open(path, "r", encoding="utf-8").read()
    begin = "<!-- PACKAGES:BEGIN -->"
    end = "<!-- PACKAGES:END -->"
    if begin not in text or end not in text:
        raise ValueError("index.html missing %s / %s markers" % (begin, end))
    cards = []
    for package in meta.packages:
        variants = sort_variants(package)
        cards.append(render_card(package, meta.repo, variants))
    new = text.split(begin)[0] + begin + "\n" + "\n".join(cards) + "\n    " + end + \
        text.split(end, 1)[1]
    with open(path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(new)


# ---------------------------------------------------------------- checks


def check(repo_dir, meta, debs, mapping):
    errors = []
    idx = os.path.join(repo_dir, "Packages")
    text = open(idx, "r", encoding="utf-8").read()
    stanzas = [s for s in text.split("\n\n") if s.strip()]
    if len(stanzas) != len(debs):
        errors.append("Packages stanza count %d != deb count %d" % (len(stanzas), len(debs)))

    seen = set()
    for stanza in stanzas:
        fields = parse_control(stanza)
        pkg = get_field(fields, "Package")
        ver = get_field(fields, "Version")
        arch = get_field(fields, "Architecture")
        key = (pkg, ver, arch)
        if key in seen:
            errors.append("duplicate stanza %s" % (key,))
        seen.add(key)
        fn = get_field(fields, "Filename")
        size = get_field(fields, "Size")
        sha = get_field(fields, "SHA256")
        path = os.path.join(repo_dir, fn)
        if not os.path.isfile(path):
            errors.append("missing deb %s" % fn)
            continue
        if str(os.path.getsize(path)) != size:
            errors.append("size mismatch %s" % fn)
        if sha256_of(path) != sha:
            errors.append("sha256 mismatch %s" % fn)
        for required in ("Name", "Description", "Homepage", "SileoDepiction", "Depiction"):
            if not get_field(fields, required):
                errors.append("%s missing %s" % (fn, required))

    for package in meta.packages:
        variants = sort_variants(package)
        if not variants:
            errors.append("%s has no variants" % package["package"])
        for variant in variants:
            key = (package["package"], variant["version"], variant["arch"])
            if key not in mapping:
                errors.append("metadata variant without deb: %s" % (key,))
        dep_path = os.path.join(repo_dir, "sileodepictions", package["package"], "index.json")
        web_path = os.path.join(repo_dir, "depictions", package["package"], "index.html")
        if not os.path.isfile(dep_path):
            errors.append("missing depiction %s" % dep_path)
        else:
            try:
                data = json.load(open(dep_path, "r", encoding="utf-8"))
                tabs = [t.get("tabname") for t in data.get("tabs", [])]
                for name in ("功能", "兼容性", "更新日志", "反馈"):
                    if name not in tabs:
                        errors.append("%s missing tab %s" % (dep_path, name))
            except Exception as exc:
                errors.append("bad JSON %s: %s" % (dep_path, exc))
        if not os.path.isfile(web_path):
            errors.append("missing web depiction %s" % web_path)
        else:
            body = open(web_path, "r", encoding="utf-8").read()
            for anchor in ('id="features"', 'id="compatibility"',
                           'id="changelog"', 'id="feedback"'):
                if anchor not in body:
                    errors.append("%s missing %s" % (web_path, anchor))

    landing = open(os.path.join(repo_dir, "index.html"), "r", encoding="utf-8").read()
    if landing.count('class="pkg"') != len(meta.packages):
        errors.append("landing cards %d != packages %d" %
                      (landing.count('class="pkg"'), len(meta.packages)))
    if "http://" in landing:
        errors.append("landing contains http://")

    if errors:
        print("\n!! CHECK FAILED")
        for error in errors:
            print("   -", error)
        return False
    print("\n== CHECK OK ==")
    print("   debs: %d, packages: %d, stanzas: %d" %
          (len(debs), len(meta.packages), len(stanzas)))
    return True


# ---------------------------------------------------------------- main


def main():
    default_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=default_dir, help="repo root")
    ap.add_argument("--meta", default=None, help="repo-meta.json path")
    ap.add_argument("--check", action="store_true", help="validate after generation")
    args = ap.parse_args()

    repo_dir = os.path.abspath(args.dir)
    meta_path = args.meta or os.path.join(repo_dir, "repo-meta.json")
    meta = Meta(json.load(open(meta_path, "r", encoding="utf-8")))

    debs_dir = os.path.join(repo_dir, "debs")
    debs = []
    for fn in sorted(os.listdir(debs_dir)):
        if fn.endswith(".deb"):
            debs.append(Deb(os.path.join(debs_dir, fn), fn))
    if not debs:
        sys.exit("!! no debs in %s" % debs_dir)

    by_key = {deb.key: deb for deb in debs}
    mapping = {}
    for package in meta.packages:
        for variant in package["variants"]:
            key = (package["package"], variant["version"], variant["arch"])
            if key not in by_key:
                sys.exit("!! metadata variant has no deb: %s" % (key,))
            mapping[key] = by_key[key]
    for deb in debs:
        if deb.key not in mapping:
            sys.exit("!! deb has no metadata: %s" % (deb.key,))

    # Generated dirs are disposable.
    for name in ("sileodepictions", "depictions"):
        path = os.path.join(repo_dir, name)
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path)

    for package in meta.packages:
        variants = sort_variants(package)
        dep_dir = os.path.join(repo_dir, "sileodepictions", package["package"])
        web_dir = os.path.join(repo_dir, "depictions", package["package"])
        os.makedirs(dep_dir)
        os.makedirs(web_dir)
        data = build_sileo_depiction(package, meta.repo, variants, by_key)
        with open(os.path.join(dep_dir, "index.json"), "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        page = render_web_page(package, meta.repo, variants, by_key)
        with open(os.path.join(web_dir, "index.html"), "w", encoding="utf-8",
                  newline="\n") as fp:
            fp.write(page)
        print("  + %-42s %s" % (package["package"],
                                ", ".join(v["version"] for v in variants)))

    packages_bytes = build_packages(repo_dir, meta, debs, mapping)
    write_release(repo_dir, packages_bytes, meta)
    update_landing(repo_dir, meta, mapping)
    print("== generated Packages / Packages.gz / Packages.xz / Release ==")
    print("== generated sileodepictions/ and depictions/ ==")
    print("== updated index.html package cards ==")

    if args.check:
        ok = check(repo_dir, meta, debs, mapping)
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
