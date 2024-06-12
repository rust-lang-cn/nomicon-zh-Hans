# Rust 秘典

高级 Unsafe Rust 编程的黑科技指南

在 Rust 社区内俗称“nomicon”，另有中文译名“死灵书”[^1]。

在线阅读：[https://nomicon.purewhite.io/](https://nomicon.purewhite.io/)

[^1]: [Stephen Bell's answer to What does the word suffix '-onomicon' mean? - Quora](https://www.quora.com/What-does-the-word-suffix-onomicon-mean/answer/Stephen-Bell-2)

## 注意：本书仍为草案，其中可能包含严重错误

> 我没有寻见自己期待的程序，只感受到了令人战栗的黑暗与无法言喻的孤独；最终，我察觉到了一个可怖的真相。过去甚至没有人胆敢低声说出这一事实——这是秘密中秘密，是不能低声言及的秘密——人们一直认为这门如砖石般刺耳的语言[^2]乃是 Rust 感性的延续，就像是伦敦之于旧伦敦，巴黎之于旧巴黎，然而事实并非如此，它反而很不安全。甚至连现状都未能被固化保持，一些异样的东西正在它粗糙的语义上生机勃勃地孽生繁衍——这些东西与欲编译的它没有任何关联。[^3]
>
> 原文：
>
> > Instead of the programs I had hoped for, there came only a shuddering blackness and ineffable loneliness; and I saw at last a fearful truth which no one had ever dared to breathe before — the unwhisperable secret of secrets — The fact that this language of stone and stridor is not a sentient perpetuation of Rust as London is of Old London and Paris of Old Paris, but that it is in fact quite unsafe, its sprawling body imperfectly embalmed and infested with queer animate things which have nothing to do with it as it was in compilation.[^4]

本书深入探讨了各种令人抓狂的细节，你必须理解这些细节才能写出正确的 Unsafe Rust 代码。这种探讨可能释放出无尽恐怖，令你道心破碎；鉴于问题本质，无法避免这种情况。

[^2]: 指 Unsafe Rust

[^3]: 译文参照：[《他》 by 竹子](https://trow.cc/board/index.php?showtopic=24153)

[^4]: 本段致敬的原文：[H. P. Lovecraft Quote from "He"](https://libquotes.com/h-p-lovecraft/quote/lbr0l5j)

## 构建依赖

如果你想要自己构建《Rust 秘典》，需要使用 [mdBook]。安装方法：

[mdBook]: https://github.com/rust-lang/mdBook

```bash
cargo install mdbook
```

如果想要构建的 Html 站点支持中文搜索功能，请改用 [Sunshine40/mdBook 的 search-non-english 分支](https://github.com/Sunshine40/mdBook/tree/search-non-english)。

安装方法（这种情况下不需要按上一段步骤安装官方版本 mdBook）：

```bash
cargo install mdbook --git https://github.com/Sunshine40/mdBook --branch search-non-english --force
```

### `mdBook` 用法

为了方便一键构建《Rust 秘典》双语对照版本，建议使用：  
_(先确保工作路径位于本项目文件夹根路径)_

```bash
./build.sh
```

构建结果会存放到 `book` 子目录中。用浏览器打开其中的 `index.html` 文件即可查看效果。如果在执行 `./build.sh` 时附带 `--open` 标志，（构建成功后）它就会直接用默认浏览器打开书籍首页，和 `cargo doc --open` 同理：

```bash
./build.sh --open
```

也可以使用 `mdbook build` 命令单独构建中文版本（构建英文版本需要仿照 `build.sh` 配置参数）：

```bash
mdbook build
```

`mdbook` 还有一个 `test` 子命令用于测试书中包含的所有代码样例：

```bash
mdbook test
```

### `linkcheck`

我们使用 `linkcheck` 工具来检查失效的链接。本地执行方法:

```sh
curl -sSLo linkcheck.sh https://raw.githubusercontent.com/rust-lang/rust/master/src/tools/linkchecker/linkcheck.sh
sh linkcheck.sh --all nomicon-zh-Hans
```

## 贡献

欢迎大家一起参与《Rust 秘典》的中文简体翻译，如果你觉得有可改善之处欢迎直接 PR，我会尽快处理；或者如果你不太确定是否需要更改，也可以提一个 Issue。

翻译风格指南：https://zh-style-guide.readthedocs.io/

## 后续规划

- [x] 完成代码中注释的翻译
- [x] 完成中英文双语版本，支持页内一键切换语言
- [ ] 搭建自动发版部署流程
- [ ] 有没有可能支持更新订阅？（RSS？）或者有重要更新时邮件提醒？
- [ ] more（欢迎通过 issue 提出）
