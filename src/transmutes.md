# Transmutes

类型系统，别挡着我们的路！我们要重新解释这些比特，否则就会死掉！尽管这本书是关于做不安全的事情的，但我真的必须强调，你应该深入思考找到本节中所涉及的操作以外的另一种方法。这真的是你在 Rust 中所能做的最可怕的不安全的事情，而这基本不设防。

[`mem::transmute<T, U>`][transmute]接收一个`T`类型的值并将其重新解释为`U`类型。唯一的限制是`T`和`U`被验证为具有相同的大小。导致未定义行为的方法是令人难以置信的。

- 首先，创建一个具有无效状态的*任何*类型的实例都会导致无法真正预测的任意混乱。即使你从未对`bool`做过任何事情，也不要把`3`转化为`bool`。就是不要。
- Transmute 有一个重载的返回类型。如果你不指定返回类型，它可能会为了满足类型推导而返回一个令人惊讶的类型。
- 将一个`&`转为`&mut`是未定义行为，尽管某些用法*可能*是安全的，但是需要注意，Rust 优化器可以自由地假设一个共享引用在它的生命周期内是不变的，而这种转换会违反这个假设。因此：
  - 将一个`&`转为`&mut`*总是*未定义行为
  - 不，你不能这样做
  - 不，你并不特别
- Transmute 到一个没有明确提供生命周期的引用会产生一个[无限制的寿命][unbounded lifetime]
- 当在不同的复合类型之间转换时，你必须确保它们的布局是一样的！如果布局不同，错误的字段就会被填入错误的数据，这也许仅仅让你 Debug 一阵，也可能会造成 UB（见上文）

  那么你怎么知道布局是否相同呢？对于`repr(C)`类型和`repr(transparent)`类型，布局是精确定义的。但是对于普通的`repr(Rust)`来说，它不是。即使是同一个通用类型的不同实例也可以有截然不同的布局。`Vec<i32>`和`Vec<u32>`*可能*有相同的字段顺序，也可能没有。数据布局保证了什么，或者没保证什么的细节可以参考[ UCG 工作组][ucg-layout]。

[`mem::transmute_copy<T, U>`][transmute_copy]比这个更不安全。它把`size_of<U>`字节从`T`中复制出来，并把它们解释为`U`。`mem::transmute`的大小检查没有了（因为复制出一个前缀可能是有效的），尽管`U`比`T`大是未定义行为。

当然，你也可以使用原始指针转换或`union`来获得这些函数的所有功能，并关闭 Lint 或其他基本的合理性检查。原始指针转换和`union`并不能神奇地避免上述规则。

[unbounded lifetime]: ./unbounded-lifetimes.md
[transmute]: https://doc.rust-lang.org/std/mem/fn.transmute.html
[transmute_copy]: https://doc.rust-lang.org/std/mem/fn.transmute_copy.html
[ucg-layout]: https://rust-lang.github.io/unsafe-code-guidelines/layout.html
