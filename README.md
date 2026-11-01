# Chenlin8023 Repo

iOS 17 越狱插件源，托管在 GitHub Pages。加源地址：

```
https://chenlin8023.github.io/
```

| 插件 | 版本 | 架构 | 说明 |
|---|---|---|---|
| LSTimeSeconds | 0.0.7-1 | iphoneos-arm64e | 锁屏实时秒数 + 字号缩放 + 上下位置调节 |
| BioProtect Leak Guard | 2.0.13 | iphoneos-arm64e | BioProtect 端口/fd 泄漏修复 |
| VolumeManager (Full) | 1.2.0 | iphoneos-arm64 | 每 App 独立音量，消除爆音（rootless，RootHide 需转换） |
| VolumeManager Prefs Clean | 1.1.0 | iphoneos-arm64 | 音量设置面板净化（rootless，RootHide 需转换） |

只收录在真机（iPhone 15 Pro / iOS 17.2.1 / RootHide）验证过的构建。

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
