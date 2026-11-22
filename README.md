# Chenlin8023 Repo

iOS 16–17 越狱插件源，托管在 GitHub Pages。加源地址：

```
https://chenlin8023.github.io/
```

> 每个插件页分「功能 / 兼容性 / 更新日志 / 反馈」四块。
> 优先收录实机验证过的构建；未单独验证的版本会在更新日志里明确标注。

## 收录的插件

| 插件 | 分类 | 当前版本 | 架构 | 实机验证 | 项目仓库 |
|---|---|---|---|---|---|
| MUtool 工具箱（roothide · 授权破解版） | 系统 | 2.2.95-1（另有 2.2.89-2 / 2.2.89-1 / 2.1.66-1） | `iphoneos-arm64e` | iPhone 15 Pro / iOS 17.2.1 | [muzikeji](https://github.com/muzikeji) |
| MUtool 工具箱（rootless · 授权破解版） | 系统 | 2.2.95-2（另有 2.2.80-13） | `iphoneos-arm64` | iPhone 15 Pro / iOS 17.2.1 | [muzikeji](https://github.com/muzikeji) |
| VolumeManager (Full) | 系统 | 2.0.4（另有 2.0.3 / 1.3.4 / 1.3.0 / 1.2.0；dylib 线 2.1.4） | `iphoneos-arm64` | iPhone 15 Pro / iOS 17.2.1 | [VolumeManager-iOS17](https://github.com/Chenlin8023/VolumeManager-iOS17) |
| CallAssist PortLeak | 系统 | 2.1.0 | `iphoneos-arm64e` | 2.1.0 待确认；2.0.14 已验证（iPhone 15 Pro / iOS 17.2.1） | [CallAssist-PortLeak](https://github.com/Chenlin8023/CallAssist-PortLeak) |
| AppLock+ (应用锁+) | 系统 | 0.4.2-1 | `iphoneos-arm64e` | iPhone 15 Pro / iOS 17.2.1 | [AppLockPlus](https://github.com/Chenlin8023/AppLockPlus) |
| LSTimeSeconds (RootHide) | 锁屏 | 0.0.7-1 | `iphoneos-arm64e` | iPhone 15 Pro / iOS 17.2.1 | [LSTimeSeconds-iOS17](https://github.com/Chenlin8023/LSTimeSeconds-iOS17) |
| LSTimeSeconds (rootless) | 锁屏 | 0.0.7-5 | `iphoneos-arm64` | iPhone 14 Pro / iOS 16.0.3（0.0.7-4/5） | 同上 |
| Jikan（锁屏充电预估） | 锁屏 | 1.2.1-1+debug / 1.2.0 | `iphoneos-arm64e` | iPhone 15 Pro / iOS 17.2.1 | [Jikan](https://github.com/Chenlin8023/Jikan) |
| 应用通知小图标（NotifierIcons） | 状态栏 | 0.9.2 | `iphoneos-arm64` | iPhone 15 Pro / iOS 17.2.1 | [notifiericons](https://github.com/Chenlin8023/notifiericons) |
| Jikan 简体中文语言包 | 语言包 | 1.2.1 | `iphoneos-arm64e` | iPhone 15 Pro / iOS 17.2.1 | [Jikan](https://github.com/Chenlin8023/Jikan) |

> 分类按插件**生效场景**：系统（工具箱 / 音量 / 安全 / 泄漏治理）、锁屏、状态栏、语言包。
> 分类同步写入 Packages 的 `Section` 字段（Sileo 按此归组）与插件详情页；本源暂无纯「桌面」生效插件。

### 关键说明

- **LSTimeSeconds 已拆成两个 Package ID**：
  - RootHide：`com.sini921.lstimeseconds.roothide`（`0.0.7-1`，arm64e）
  - rootless：`com.sini921.lstimeseconds`（`0.0.7-5 / -4 / -2`，arm64，`/var/jb`）
  - 从旧版 RootHide 包升级必须先卸载旧 `com.sini921.lstimeseconds`，再装新的 `.roothide` 包；
    prefs 域仍是 `com.b4db1r3.lstsprefs`，设置可保留。两包互相 `Conflicts`，不能共存。
- **CallAssist 当前发布包仍是旧 ID**：项目已更名 `CallAssistLeakGuard`，但源内 2.1.0 的
  Package 仍是 `com.local.callassistportleak`；2.1.0 更名重建与真机确认待完成。
- **MUtool 两条修改线互斥**：roothide 线（`com.muzi.mutool`，2.2.95-1）与 rootless 线
  （`byg.iosios.net.mutool`，2.2.95-2）目标文件路径相同、不可共存，安装其一前先卸载另一条线。
- **VolumeManager (Full)**：现役 2.0.4；另有 dylib 纯注入形态 `com.local.volmanaudioqueue.dylib`
  2.1.4（AppLock+ 同款免闸门容器）。历史版本 2.0.3 / 1.3.4 / 1.3.0 / 1.2.0 保留可回退。
- **未单独验证的版本**：LSTimeSeconds `0.0.7-2` 保留在历史里，但标注“未单独验证”；
  0.0.7-4 已覆盖其修复。

## 版本历史 / 回退

- **Sileo**：对已安装的包，长按插件页的「修改 / MODIFY」按钮，在菜单里选择历史版本。
  未安装时 Sileo 只显示最新版——这是 Sileo 客户端限制，不是源少发了版本。
- **Irisin / Zebra**：包页的版本列表可以直接选择旧版本。
- 每个插件页的「更新日志」页签列出全部版本、变更点、验证状态和该版本 `.deb` 直链。

## 反馈

统一走 GitHub Issue 表单：

```
https://github.com/Chenlin8023/Chenlin8023.github.io/issues/new?template=package-feedback.yml
```

请附：插件版本、机型、iOS 版本、越狱环境、安装/注入方式、复现步骤、日志或截图。

## 目录

```
.
├── index.html          # 落地页（包卡片由生成器写入）
├── repo-meta.json      # 每个包的功能/兼容性/更新日志/反馈元数据
├── tools/make_repo.py  # 生成器
├── Packages            # APT 索引（生成）
├── Packages.gz
├── Packages.xz
├── Release             # 源元信息 + 索引哈希（生成）
├── sileodepictions/    # Sileo 原生富页面（生成）
├── depictions/         # Zebra / Cydia / Irisin 的 Web Depiction（生成）
└── debs/               # 安装包
```

## 发布新版本

1. 把新 `.deb` 放进 `debs/`。
2. 在 `repo-meta.json` 里补上该版本的 `variants` 条目（版本、日期、架构、机型、iOS、
   验证状态、变更点）。
3. 重新生成并校验：

```bash
python tools/make_repo.py --check
```

4. `git add -A && git commit -m "repo: 发布 xxx" && git push`。
5. 若 `github.com:443` 不通，用 `../tools/push_update.py` 走 `api.github.com` 推送。
6. 推送后核对：

```bash
curl -s https://chenlin8023.github.io/Packages | sha256sum
curl -s https://chenlin8023.github.io/sileodepictions/com.sini921.lstimeseconds.roothide/index.json
```

> 生成器只改索引与页面，不碰 `.deb`。`Packages` 里的 Package/Version/Architecture/
> Depends/Conflicts/Replaces 全部来自 deb 的 control，避免索引与实际安装包不一致。
