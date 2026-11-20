"""终端可见导览、现场通行表和志愿者公告台。"""
from argparse import ArgumentParser
from html import escape
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent


def create_source(port=0, root=ROOT):
    def records(name):
        return json.loads((root / "data" / (name + ".json")).read_text())

    pages = {tuple(f["scope"]): f for f in records("terminals")}
    schedule = records("sessions")
    published = {item["ref"]: item for item in records("briefings")}
    messages = {}
    visits = {}
    current = 1
    serial = 0

    class Kiosk(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def visual(self, title, content, code=200, token=""):
            body = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><title>{title}</title>
            <style>body{{font:16px system-ui;max-width:64rem;margin:2rem auto;padding:0 1rem}}
            a,button,select{{display:inline-block;margin:.4rem;padding:.3rem}}[role=button]{{cursor:pointer;color:#286154}}
            [hidden]{{display:none !important}}:focus-visible{{outline:3px solid #bd7400}}td,th{{padding:.3rem;text-align:left}}</style>
            <nav><a href="/">终端连接</a><a href="/venue">现场通行</a><a href="/notice">志愿者公告台</a>
            <a href="/publish-plan">班前发布单</a><a href="/ops">现场演练轮次</a></nav>
            <main><h1>{title}</h1><p>当前轮次 {current}</p>{content}</main></html>""".encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if token:
                self.send_header("Set-Cookie", f"kiosk={token}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(body)

        def redirect(self, destination, token=""):
            self.send_response(303)
            self.send_header("Location", destination)
            if token:
                self.send_header("Set-Cookie", f"kiosk={token}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()

        def table(self, name, labels, rows):
            heading = "".join(f"<th>{label}</th>" for label in labels)
            entries = "".join("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>" for row in rows)
            return f'<table aria-label="{name}"><thead><tr>{heading}</tr></thead><tbody>{entries}</tbody></table>'

        def current_visit(self):
            jar = SimpleCookie(self.headers.get("Cookie"))
            return visits.get(jar["kiosk"].value) if "kiosk" in jar else None

        def home(self):
            selectors = (
                ("terminal", "终端", ("K1", "K2")),
                ("entry", "入口", ("E1", "E2")),
                ("lang", "语言", ("zh", "en")),
                ("mode", "操作方式", ("keyboard", "touch")),
            )
            fields = "".join(f'<label for="{name}">{label}</label><select id="{name}" name="{name}">' + "".join(f'<option>{x}</option>' for x in options)
                             + "</select>" for name, label, options in selectors)
            windows = [([row[k] for k in ("terminal", "from", "until")]) for row in schedule]
            body = self.table("检查时窗", ("终端", "起始轮", "结束轮"), windows)
            self.visual("工坊导览连接", body + f'<form method="post" action="/connect">{fields}<button>进入导览</button></form>')

        def do_GET(self):
            url = urlsplit(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/":
                return self.home()
            if url.path == "/ops":
                return self.visual("现场演练轮次", '<form method="post" action="/ops"><label>下个轮次<input name="turn"></label>'
                                   '<button>推进轮次</button></form>')
            if url.path == "/guide":
                state = self.current_visit()
                if not state or not state["active"] or current >= state["until"]:
                    return self.visual("终端已返回首页", '<a href="/">重新连接</a>', 409)
                return self.guide(state)
            if url.path == "/venue":
                source = [x for x in records("access") if x["round"] <= current]
                fields = [([*row["route"], ",".join(row["groups"]), row["from"], row["until"], row["round"]])
                          for row in source]
                return self.visual("现场通行", self.table("有向通行表",
                                   ("起点", "终点", "通行组", "开放时间", "关闭时间", "公告轮"), fields))
            if url.path == "/publish-plan":
                plans = records("assignments")
                return self.visual("班前发布单", self.table("发布任务",
                   ("单号","终端","入口","语言","方式","通行组","活动","带队时段","服务点"),
                   [[row["id"],*row["scope"],",".join(row["modes"]),",".join(row["groups"]),
                     ",".join(row["activities"]),"-".join(row["service"]),",".join(row["teams"])] for row in plans]))
            if url.path == "/notice":
                return self.notice(q)
            self.visual("无此页面", "", 404)

        def notice(self, query):
            rows = [[r["ref"], r["assignment"], r["activity"], r["mode"], r["group"],r["route"],
                     " → ".join(r["points"]), "-".join(r["service"]), r["team"], r.get("status", "已读")]
                    for r in published.values()]
            base = self.table("已送指引", ("交接号","发布单","活动","方式","通行组","路线",
                                           "检查点","适用时间","服务点","状态"), rows)
            ref = query.get("ref", "")
            if ref:
                msg = messages.get(ref)
                if msg and msg["known"] <= current:
                    base += "<p>通知回条 " + escape(ref) + " " + escape(msg["state"]) + "</p>"
                else:
                    base += "<p>通知回条尚未显示</p>"
            base += ('<form action="/notice"><label>查询通知号<input name="ref"></label><button>查询通知</button></form>'
                     '<form method="post" action="/notice"><label>通知号<input name="ref"></label>'
                     '<label>原交接号<input name="previous"></label><label>服务点<input name="team"></label>'
                     '<label>停发时间<input name="time"></label><button>发停用通知</button></form>')
            labels = [("ref", "新交接号"), ("assignment", "发布单"), ("activity", "活动"),
                      ("mode", "方式"), ("group", "通行组"), ("route", "路线"),
                      ("points", "检查点序列"), ("start", "适用起始"), ("end", "适用结束"), ("team", "领用服务点")]
            fields = "".join(f'<label>{label}<input name="{name}" required></label>' for name, label in labels)
            base += '<form method="post" action="/notice/publish">' + fields + '<button>发布新指引</button></form>'
            return self.visual("志愿者公告台", base)

        def guide(self, state):
            terminal, entry, lang, release = state["scope"]
            config = pages[state["scope"]]
            section = state["node"]
            nodes = config["pages"]
            if section not in nodes:
                return self.visual("导览尚未更新", '<a href="/">重新连接</a>', 409)
            row = nodes[section]
            payload_version = row.get("installed", config["version"])
            if "installed" in row and current >= row.get("corrected_at", 99):
                payload_version = config["version"]
            values = (terminal, entry, lang, state["mode"], release, config["version"], payload_version)
            context = "<dl>" + "".join(f"<dt>{key}</dt><dd>{escape(value)}</dd>" for key, value in zip(
                ("终端", "入口", "语言", "方式", "发布批次", "首页版本", "本页安装版"), values
            )) + "</dl>"
            form = ('<form action="/step" method="post"><button name="step" value="home">导览首页</button>'
                    '<button name="step" value="release">结束检查</button>')
            for node, label, mode in row.get("links", []):
                if mode == "pointer":
                    form += f'<span role="button" onclick="this.nextElementSibling.click()">{escape(label)}</span>'
                    form += f'<button hidden name="step" value="{node}">{escape(label)}</button>'
                else:
                    form += f'<button name="step" value="{node}">{escape(label)}</button>'
            form += "</form>"
            guides = ""
            for route in row.get("guides", []):
                items = "".join(f"<li>{escape(str(p))}</li>" for p in route.get("points", []))
                guides += f'<section><h2>{route["activity"]} {route["route"]}</h2><p>{route["state"]}</p><ol>{items}</ol></section>'
            if row.get("dialog"):
                text = escape(row["dialog"])
                modal = f'<dialog id="details"><p>{text}</p><form method="dialog"><button autofocus>继续</button></form></dialog>'
                return self.visual(escape(row["title"]), context + form + guides + modal
                                   + '<script>document.getElementById("details").showModal()</script>')
            return self.visual(escape(row["title"]), context + form + guides)

        def do_POST(self):
            nonlocal current, serial
            args = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            values = {key: item[0] for key, item in args.items()}
            if self.path == "/ops":
                target = values.get("turn", "")
                if not target.isdecimal() or int(target) < current:
                    return self.visual("轮次不能倒退", "", 409)
                current = int(target)
                for message in messages.values():
                    if message["read_at"] <= current:
                        message["state"] = "停发已读"
                        published[message["previous"]]["status"] = "停发已读"
                return self.redirect("/ops")
            if self.path == "/connect":
                if not all(k in values for k in ("terminal", "entry", "lang", "mode")):
                    return self.visual("缺少范围", "", 422)
                term = values["terminal"]
                available = next((row for row in schedule if row["terminal"] == term and
                                  row["from"] <= current < row["until"]), None)
                if not available or any(v["scope"][0] == term and v["active"] and v["until"] > current for v in visits.values()):
                    return self.visual("终端检查时段不可用", '<a href="/">查看时窗</a>', 409)
                scope = (term, values["entry"], values["lang"], available["release"])
                if scope not in pages:
                    return self.visual("未发布所选范围", "", 404)
                serial += 1
                token = str(serial)
                visits[token] = {"scope": scope, "mode": values["mode"], "until": available["until"],
                                 "node": "home", "active": True}
                return self.redirect("/guide", token=token)
            if self.path == "/step":
                state = self.current_visit()
                if not state or not state["active"] or current >= state["until"]:
                    return self.redirect("/")
                next_step = values.get("step")
                if next_step == "release":
                    state["active"] = False
                    return self.redirect("/")
                if next_step == "home" or next_step in [dest for dest, _, _ in
                        pages[state["scope"]]["pages"].get(state["node"], {}).get("links", [])]:
                    state["node"] = next_step
                    return self.redirect("/guide")
                return self.visual("当前界面没有此下一步", "", 422)
            if self.path == "/notice":
                return self.submit_notice(values)
            if self.path == "/notice/publish":
                return self.submit_guide(values)
            self.visual("无此页面", "", 404)

        def submit_notice(self, values):
            ref, previous, team = (values.get(key) for key in ("ref", "previous", "team"))
            if not ref or previous not in published or published[previous]["team"] != team or "time" not in values:
                return self.visual("停发通知须有具体交接和接收人", "", 422)
            if ref in messages and messages[ref]["input"] != values:
                return self.visual("通知号内容有冲突", "", 409)
            if ref not in messages:
                messages[ref] = {"input": values, "previous": previous, "known": current+1,
                                 "state": "停发已送", "read_at": current+2}
                published[previous]["status"] = "停发已送"
            return self.redirect("/notice?" + urlencode({"ref": ref}))

        def submit_guide(self, values):
            fields = ("ref", "assignment", "activity", "mode", "group", "route", "points", "start", "end", "team")
            if any(not values.get(name) for name in fields) or values["start"] >= values["end"]:
                return self.visual("指引单缺少范围", "", 422)
            if values["ref"] in published:
                if published[values["ref"]].get("input") != values:
                    return self.visual("交接号内容有冲突", "", 409)
                return self.redirect("/notice")
            plans = {p["id"]: p for p in records("assignments")}
            plan = plans.get(values["assignment"])
            if not plan or values["team"] not in plan["teams"]:
                return self.visual("未找到发布范围", "", 404)
            published[values["ref"]] = {**values, "points": values["points"].split(","),
                                        "service": [values["start"], values["end"]], "status": "已送达",
                                        "input": values}
            return self.redirect("/notice")

    return HTTPServer(("127.0.0.1", port), Kiosk)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8040)
    with create_source(parser.parse_args().port) as server:
        print(f"导览终端在 http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()
