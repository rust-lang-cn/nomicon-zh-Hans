# Rust 秘典

高级和不安全 Rust 编程的黑魔法指南。

绰号“死灵书”。

地址：[https://nomicon.purewhite.io/](https://nomicon.purewhite.io/)

## 注意：这本书仍处于草稿状态，可能包含严重的错误。

> 我所希望的程序没有出现，而是出现了令人战栗的黑暗和不可言喻的孤独。我终于看到了一个可怕的事实，以前从来没有人敢说出来——秘密中不可告人的秘密——这个事实是，这种石头和声音的语言并不是 Rust 的有生命的延续，就像伦敦是老伦敦，巴黎是老巴黎一样，但它实际上是很不安全的，它的蔓延的身体并没有完善地被防腐处理，并且被诡异的动态的东西侵扰，并且这些东西在编译时无能为力。
>
> 原文：
> > Instead of the programs I had hoped for, there came only a shuddering blackness and ineffable loneliness; and I saw at last a fearful truth which no one had ever dared to breathe before — the unwhisperable secret of secrets — The fact that this language of stone and stridor is not a sentient perpetuation of Rust as London is of Old London and Paris of Old Paris, but that it is in fact quite unsafe, its sprawling body imperfectly embalmed and infested with queer animate things which have nothing to do with it as it was in compilation.

本书挖掘了所有可怕的细节，为了写出正确的不安全 Rust 程序，这些细节是必须要了解的。由于这个问题的性质，它可能会导致释放出难以言喻的恐怖，将你的心灵打碎成亿万个绝望的微小碎片。

## Requirements

如果你需要自己构建死灵书，需要[mdBook]：

[mdBook]: https://github.com/rust-lang/mdBook

```bash
cargo install mdbook
```

### `mdbook`用法

构建死灵书，请使用`build`命令：

```bash
mdbook build
```

产物将被放置在`book`子目录下。如果你想打开它，可以在你的浏览器中打开`index.html`文件。你可以给`mdbook build`传递`--open`标志，它将在你的默认浏览器中打开索引页（如果过程成功），就像使用`cargo doc --open`一样。

```bash
mdbook build --open
```

还有一个`test`子命令来测试书中包含的所有代码样本。

```bash
mdbook test
```

### `linkcheck`

我们使用`linkcheck`工具来查找失效的链接：

```sh
curl -sSLo linkcheck.sh https://raw.githubusercontent.com/rust-lang/rust/master/src/tools/linkchecker/linkcheck.sh
sh linkcheck.sh --all nomicon-zh-Hans
```

## 贡献

欢迎大家一起参与《Rust 秘典》的中文简体翻译，如果你觉得有可改善之处欢迎直接 PR，我会尽快处理；或者如果你不太确定是否需要更改，也可以提一个 Issue。

翻译风格指南：https://zh-style-guide.readthedocs.io/

## RoadMap

- [ ] 完成代码中注释的翻译
- [ ] 搭建自动发版部署流程
- [ ] 完成中英文对照版本，并默认隐藏英文
- [ ] 有没有可能支持更新订阅？（RSS？）或者有重要更新时邮件提醒？
- [ ] more（欢迎通过 issue 提出）
