# Chenlin8023 Repo

iOS 17 越狱插件源，托管在 GitHub Pages。加源地址：

```
https://chenlin8023.github.io/
```

| 插件 | 版本 | 架构 | 实机验证 | 说明 |
|---|---|---|---|---|
| NotifierIcons | 0.9.2 | iphoneos-arm64 | iOS 17.2.1 | 状态栏应用通知图标（安卓通知语义） |
| AppLock+ (应用锁+) | 0.4.2-1 | iphoneos-arm64e | iOS 17.2.1 | 按应用注入式应用锁（载体包，需 TrollFools/JailFools 注入） |
| CallAssist PortLeak | 2.1.0 | iphoneos-arm64e | iOS 17.2.1 | CallAssist IOKit 轮询端口泄漏的侦查与止血 |
| LSTimeSeconds (RootHide) | 0.0.7-1 | iphoneos-arm64e | iOS 17.2.1 | 锁屏实时秒数 + 字号缩放 + 上下位置调节 |
| LSTimeSeconds (rootless) | 0.0.7-5 | iphoneos-arm64 | iOS 16.0.3 | 同上，`/var/jb` 版本；修复熄屏唤醒冻结，增加日志轮转与秒针对齐 |
| VolumeManager (Full) | 1.3.0 | iphoneos-arm64 | iOS 17.2.1 | 每个 App 独立音量、多 App 同时播放；修静音长时间播放后失效（rootless，RootHide 需转换；注入过的 App 升级后需重新注入引擎） |
| VolumeManager Prefs Clean | 1.1.0 | iphoneos-arm64 | iOS 17.2.1 | 音量设置面板净化（rootless，RootHide 需转换） |

只收录在真机验证过的构建。LSTimeSeconds rootless 0.0.7-4/5 在 iOS 16.0.3 验证，其余包在 iOS 17.2.1 验证。

> 架构可见性：普通 rootless / rootful 设备的 APT 架构是 `iphoneos-arm64` / `iphoneos-arm`，
> Sileo 会过滤掉 `iphoneos-arm64e` 的 roothide 包，所以看不到 AppLock+、CallAssist、
> LSTimeSeconds (RootHide)；RootHide 设备通常同时启用 arm64e 与 arm64，两种都能看到。

## 目录

```
.
├── index.html      # 落地页
├── Packages        # APT 索引（make_repo.py 生成）
├── Packages.gz
├── Packages.xz
├── Release         # 源元信息 + 索引哈希
└── debs/           # 安装包
```

## 发布新版本

```bash
cp 新包.deb debs/
python3 ../LSTimeSeconds-iOS17/tools/make_repo.py --dir .
git add -A && git commit -m "repo: 发布 xxx" && git push
```

索引生成器见 <https://github.com/Chenlin8023/LSTimeSeconds-iOS17/tree/master/tools>。
