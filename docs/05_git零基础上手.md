# Git 零基础配置（Windows，30 分钟，每步都有验证）

> 为什么必须先搞这个：入队要求第 4 条是"有项目经历"。**GitHub 上有一个提交记录清晰的仓库，
> 就是项目经历的可验证证据**；而"我做过"三个字，没有任何证据。
> 而且队里协作、看开源代码（RM 视觉开源全是 GitHub）都绕不开它。

每个代码块后面都有「验证」。**验证不通过不要往下走**，否则后面全是玄学错误。

---

## 0. 检查有没有装

```powershell
git --version
```
- 有输出（如 `git version 2.4x`）→ 跳到第 1 节
- 提示"不是内部或外部命令"→ 去 https://git-scm.com/download/win 下 64-bit 安装包

安装时**只有一个选项要改**：`Adjusting your PATH environment` 选
**"Git from the command line and also from 3rd-party software"**（默认就是它）。
其余一路 Next。装完**关掉所有终端重新开**（PATH 才会生效）。

验证：`git --version` 有输出。

---

## 1. 一次性身份配置（只做一次）

```powershell
git config --global user.name "你的名字或ID"
git config --global user.email "你的邮箱@example.com"
git config --global core.autocrlf true
git config --global init.defaultBranch main
git config --global core.editor notepad
git config --global core.quotepath false
```

逐条为什么：

| 配置 | 作用 | 不配的后果 |
|---|---|---|
| `user.name/email` | 每次提交的作者信息 | 提交记录显示 `unknown`，不能算你的贡献 |
| `core.autocrlf true` | Windows 换行转 LF | 文件整天显示"被修改"，diff 全是红绿噪音 |
| `init.defaultBranch main` | 新仓库主分支叫 main | 和 GitHub 默认不一致，push 时多一步 |
| `core.editor notepad` | 需要写提交信息时用记事本 | 默认进 vim，**新手会卡在里面出不来**（这是第一大坑） |
| `core.quotepath false` | 中文文件名正常显示 | 中文变成 `\344\270\255` 这种乱码 |

验证：
```powershell
git config --global --list
```
能看到上面几行。

> `core.editor` 如果你装了 VS Code，可以改成 `git config --global core.editor "code --wait"`。
> 没装就用 notepad，别用 vim。

---

## 2. 连上 GitHub（SSH，推荐）

### 2.1 生成密钥

```powershell
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
```
连续按 3 次回车（不要设密码，初学阶段设了每次都要输，很烦）。

生成在 `C:\Users\你的用户名\.ssh\` 下：`id_ed25519`（私钥，**永远不要发给任何人**）和 `id_ed25519.pub`（公钥）。

### 2.2 复制公钥

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
```
（这条命令直接把公钥放进剪贴板）

### 2.3 贴到 GitHub

GitHub → 右上角头像 → **Settings** → 左栏 **SSH and GPG keys** → **New SSH key**
→ Title 随便写（如 `my-laptop`）→ Key 里粘贴 → **Add SSH key**

### 2.4 验证

```powershell
ssh -T git@github.com
```
第一次会问 `Are you sure you want to continue connecting?` → 输入 `yes` 回车。

期望输出：`Hi 你的用户名! You've successfully authenticated...`

> **如果卡住 10 秒以上然后超时**（国内常见，22 端口被封）：建一个文件
> `C:\Users\你的用户名\.ssh\config`（无扩展名），内容：
> ```
> Host github.com
>   HostName ssh.github.com
>   Port 443
>   User git
> ```
> 再跑一次 `ssh -T git@github.com`。
>
> **如果还是不行**：退回到 HTTPS + Token 方式（见文末"备用方案"），别在这里耗一晚上。

---

## 3. 建第一个仓库（就是你现在的这个项目）

### 3.1 先写 .gitignore（**关键，顺序不能反**）

在项目根目录 `rm_autoaim_k230\` 里新建 `.gitignore`（仓库里已经给你放了一份）。
它决定"哪些文件不进仓库"。**先写好再 `git add`**，否则大文件进去了要费劲删。

### 3.2 初始化并提交

```powershell
cd C:\Users\llhh\Documents\deepseek-harness\default-workspace\rm_autoaim_k230
git init
git add .
git status
```

**停在这里看 `git status` 的输出**：列出的是"将要提交的文件"。
确认里面**没有** `venv/`、`*.kmodel`、`*.onnx`、数据集、`.pyc`。

如果发现了不该提交的 → 回到 `.gitignore` 加上它，然后 `git rm --cached 文件名`。

```powershell
git commit -m "init: 自瞄学习工程骨架（文档+参考实现）"
```

验证：
```powershell
git log --oneline
```
能看到你刚才那一条。

### 3.3 推到 GitHub

先在 GitHub 网页上 **New repository**：名字 `rm-autoaim-k230`，
**不要**勾 "Add a README"（勾了会和本地冲突）。

```powershell
git remote add origin git@github.com:你的用户名/rm-autoaim-k230.git
git push -u origin main
```

验证：刷新 GitHub 页面，文件都在。

> `-u` 只需要第一次加，之后直接 `git push` 就行。

---

## 4. 日常只用这 5 条

```powershell
git status                  # 现在有哪些改动（每次动手前先看一眼）
git diff                    # 具体改了什么（提交前看一眼，防手滑）
git add .                   # 把改动放进暂存区
git commit -m "说明"        # 存一个快照
git push                    # 传到 GitHub
```

**心法：`status` 和 `diff` 是你最好的朋友。** 90% 的 Git 事故是"没看就提交"。

---

## 5. 提交信息怎么写（面试官真的会看）

不合格：`update`、`fix`、`123`、`asdf`
合格：
```
feat: 用 bbox 高度实现单目测距，3m 误差 4.2%
fix: 修正 pitch 符号，之前云台反向
docs: 补相机标定步骤和打靶记录表
chore: 加 .gitignore，排除 kmodel 和数据集
```

前缀用 `feat/fix/docs/refactor/chore` 就够了（这是 Conventional Commits 的简化版）。

**为什么重要**：你的 `git log` 就是你的项目简历。一个每 2 小时提交一次、
信息清楚的仓库，等于把"我有工程习惯"写在了脸上。

---

## 6. 三大坑（都会踩，提前知道能省一天）

### 坑 1：`.gitignore` 写晚了，把 kmodel / 数据集提交进去了

```powershell
git rm --cached model/xxx.kmodel     # 从仓库移除，但保留本地文件
git commit -m "chore: 移除大文件"
```
> `.kmodel`、`.onnx`、`venv/`、`dataset/`、`*.mp4`、`*.csv` 一律不进仓库。
> 仓库超过 100 MB 后 push 会非常痛苦，而且历史里的文件删不干净。

### 坑 2：进了 vim 出不来

按 `Esc`，然后输入 `:wq` 回车（保存退出），或 `:q!` 回车（不保存退出）。
根治办法是第 1 节的 `core.editor notepad`。

### 坑 3：`push` 被拒绝（rejected / fetch first）

说明 GitHub 上有你本地没有的提交（比如你在网页上改了 README）。
```powershell
git pull --rebase origin main
git push
```
不要用 `git push -f`（强制推送）——会覆盖别人的东西，团队协作里是大忌。

---

## 7. 分支（第 2 周再学，现在只要知道概念）

| 概念 | 一句话 |
|---|---|
| `main` | 主分支，随时处于"能跑"的状态 |
| branch | 从 main 切一条副本去改，改坏了不影响 main |
| PR (Pull Request) | 把分支合并回 main 的申请，队里靠它做代码审查 |

最小用法（等你要改一个"实验性大改动"时再用）：
```powershell
git checkout -b feat/ballistics    # 新建并切到分支
# ...改代码...
git add . ; git commit -m "feat: 弹道查表"
git push -u origin feat/ballistics # 推分支
# 然后在 GitHub 网页上点 Compare & pull request
git checkout main                  # 切回主分支
```

---

## 8. 和这个项目绑定的用法（建议照做）

每完成 `docs/01_三天计划.md` 里的一个 checkpoint，就提交一次：

| checkpoint | 提交信息 |
|---|---|
| C1-1 | `feat: 相机取帧跑通，640x360@58fps` |
| C1-2 | `feat: 单类装甲板模型上板，5m 漏检 3/100` |
| C1-3 | `refactor: detector 统一输出 xyxy，修固件返回格式差异` |
| C2-1 | `feat: bbox 高度测距，3m 误差 4.2%` |
| C2-2 | `feat: 坐标系变换 + 单元测试全通过` |
| C3-1 | `feat: 弹道查表，k=0.02 由 3/5/7m 打靶数据拟合` |

三天下来 6 个提交，`git log` 就是一份完整的开发日志。**这是你入队面试时最硬的证据材料。**

---

## 9. 验收清单（全过 = Git 这关结束）

- [ ] `git --version` 有输出
- [ ] `git config --global --list` 里有 name / email / autocrlf
- [ ] `ssh -T git@github.com` 显示 successfully authenticated
- [ ] 项目已推到 GitHub，网页上能看到 `docs/` 下的 5 份文档
- [ ] `git status` 显示 `nothing to commit, working tree clean`
- [ ] 随便改一个文件，`git diff` 能看到具体改动，再改回来
- [ ] 能独立完成一次"改文件 → add → commit → push"

---

## 备用方案：HTTPS + Token（SSH 实在不通时）

1. GitHub → Settings → Developer settings → **Personal access tokens** → Tokens (classic)
   → Generate new token → 勾 **repo** → 生成后**立刻复制**（只显示一次）
2. 远程地址改成 HTTPS：
   ```powershell
   git remote set-url origin https://github.com/你的用户名/rm-autoaim-k230.git
   ```
3. 第一次 push 会弹窗要账号密码：**密码处填那个 token**，不是你的登录密码。
4. 想免输：装 Git Credential Manager（Git for Windows 自带），会自动记住。

---

## 最后一个提醒

以后你在 Ubuntu / WSL 里做 ROS 2，**Git 要重新配一遍**
（`user.name`、`email`、SSH 密钥都在各自的家目录里，互不相通）。
配法完全一样，只是 `core.autocrlf` 改成 `input`（Linux 不需要转换）。
