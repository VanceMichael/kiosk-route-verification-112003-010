# 工坊自助导览和通行表

本地演练资料使用虚构的实物、机构和记录编号。经营单据存放于 `data/`，包括 `assignments.json`、`access.json`、`briefings.json`、`terminals.json`。来源原件在提供时由资料端送出。

## 资料约定

发布单校验单位为终端、入口、语言、模式、活动和版本。活动码、路线码与检查点是服务点之间使用的简码。场馆通行表用相邻有向检查点定义路段，发布轮次与适用人群均在条目中。一路有任何一段未知或关闭，该路须经现场核对才可再次发布。终端资料的 cancelled 是活动取消。菜单不可到达与终端提示更新均不是取消证据。

用浏览器访问本地端口。请求、台账和原件均为合成资料。重启服务后恢复到演练开始时的页面和登记状态。

## 运行资料端

浏览器检查使用 Playwright 1.56.0 附带的 Chromium。已有安装可直接运行；新环境先执行 `python3 -m pip install -r requirements.txt` 和 `python3 -m playwright install --with-deps chromium`。

```sh
python3 kiosk.py --port 8040
```

以下命令核对本地资料服务和交互。

```sh
python3 -m unittest discover -s tests -v
```
