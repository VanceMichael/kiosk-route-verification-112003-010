"""现场自助导览终端。"""
from argparse import ArgumentParser
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit


ROOT = Path(__file__).resolve().parent


def create_source(port=0, root=ROOT):
    files = json.loads((root / "data/terminals.json").read_text(encoding="utf-8"))
    pages = {tuple(f["scope"]): f for f in files}

    class Kiosk(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def visual(self, title, content, code=200):
            body = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>{title}</title>
            <style>body{{font:16px system-ui;max-width:50rem;margin:3rem auto;padding:0 1rem}}
            a,button,select{{display:inline-block;margin:.4rem;padding:.3rem}}[role=button]{{padding:.4rem;cursor:pointer;color:#286154}}
            :focus-visible{{outline:3px solid #bd7400}}</style><main><h1>{title}</h1>{content}</main></html>""".encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/":
                selectors = (
                    ("terminal", "终端", ("K1", "K2")),
                    ("entry", "入口", ("E1", "E2")),
                    ("lang", "语言", ("zh", "en")),
                    ("round", "发布轮次", ("1", "2")),
                )
                fields = "".join(f'<label>{label}<select name="{name}">' + "".join(f'<option>{x}</option>' for x in options)
                                 + "</select></label>" for name, label, options in selectors)
                self.visual("工坊导览", f'<form action="/guide">{fields}<button>进入导览</button></form>')
                return
            scope = tuple(q.get(k) for k in ("terminal", "entry", "lang", "round"))
            config = pages.get(scope)
            if url.path != "/guide" or config is None:
                self.visual("无此发布范围", '<a href="/">返回</a>', 404)
                return
            source = {**q, "page": "home"}
            context = "<dl>" + "".join(f"<dt>{k}</dt><dd>{escape(v)}</dd>" for k, v in zip(
                ("终端", "入口", "语言", "发布轮次", "界面版本"), (*scope, config["version"]))) + "</dl>"
            context += f'<a href="/guide?{urlencode(source)}">导览首页</a>'
            section = q.get("page", "home")
            nodes = config["pages"]
            if section not in nodes:
                self.visual("导览已更新", context, 409)
                return
            row = nodes[section]
            content = ""
            for node, label, input_mode in row.get("links", []):
                href = "/guide?" + urlencode({**q, "page": node})
                if input_mode == "pointer":
                    content += f"""<span role="button" onclick="location.href='{href}'">{escape(label)}</span>"""
                else:
                    content += f'<a href="{href}">{escape(label)}</a>'
            for guide in row.get("guides", []):
                points = "".join(f"<li>{escape(p)}</li>" for p in guide.get("points", []))
                content += f'<section><h2>{guide["activity"]} {guide["route"]}</h2><p>{guide["state"]}</p><ol>{points}</ol></section>'
            self.visual(escape(row["title"]), context + content)

    return HTTPServer(("127.0.0.1", port), Kiosk)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8040)
    with create_source(parser.parse_args().port) as server:
        print(f"导览终端在 http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
