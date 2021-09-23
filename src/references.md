# 引用

有两种类型的引用：

* 共享的引用：`&`
* 可变引用：`&mut`

它们遵守以下规则：

* 一个引用的生命周期不能超过其所有者的生命周期
* 一个可变的引用不能被别名

这就是引用所遵循的整个模型。

当然，我们也许应该定义*别名*的含义：

```text
error[E0425]: cannot find value `aliased` in this scope
 --> <rust.rs>:2:20
  |
2 |     println!("{}", aliased);
  |                    ^^^^^^^ not found in this scope

error: aborting due to previous error
```

不幸的是，Rust 还没有真正定义其别名模型。🙀

在我们等待 Rust 的设计者明确他们语言的语义时，让我们用下一节来讨论什么是一般的别名，以及它为什么重要。
