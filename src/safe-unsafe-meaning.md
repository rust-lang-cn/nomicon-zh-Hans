# Safe 和 Unsafe 如何交互

Safe Rust 和 Unsafe Rust 之间有什么关系？它们又是如何交互的？

Safe Rust 和 Unsafe Rust 之间的边界由`unsafe`关键字控制，`unsafe`是承接了它们之间交互的桥梁。这就是为什么我们可以说 Safe Rust 是一种安全的语言：所有不安全的部分都被限制在“unsafe”边界之内。如果你愿意，你甚至可以把`#![forbid(unsafe_code)]`扔进你的代码库，以静态地保证你只写 Safe Rust。

`unsafe`关键字有两个用途：声明编译器不会保证这些代码的安全性，以及声明程序员已经确保这些代码是安全的。

在 _函数_ 和 _trait 声明_ 上添加`unsafe`前缀表示其中存在未经检查的约束。对于函数，`unsafe`意味着函数的用户必须仔细阅读该函数的文档，以确保他们的使用方式遵循了该函数规定的约束。对于 trait 声明，`unsafe`意味着 trait 的实现者必须仔细阅读 trait 文档，以确保他们的实现遵循了该 trait 规定的约束。

在代码块上添加`unsafe`前缀可以声明在其中执行的所有不安全操作都经过了验证（遵循了内部不安全操作所规定的约束）。传递给[`slice::get_unchecked`][get_unchecked]的索引在边界内时，就是一个可以这样添加`unsafe`前缀的例子。

在 trait 实现上添加`unsafe`前缀可以声明该实现满足了 trait 所规定的约束。例如，当一个类型的值移动到另一个线程是真正安全的时，便可在[`Send`]的实现前添加`unsafe`前缀。

标准库中有许多 unsafe 的函数，包括：

-   [`slice::get_unchecked`][get_unchecked]，它不会检查传入索引的有效性，允许违反内存安全的规则。
-   [`mem::transmute`][transmute]将一些数据重新解释为给定的类型，绕过类型安全的规则（详见[conversions]）。
-   每一个指向一个 Sized 类型的原始指针都有一个[`offset`][ptr_offset]方法，如果传递的偏移量不在[“界内”][ptr_offset]，则该调用是未定义行为。
-   所有 FFI（外部函数接口 Foreign Function Interface）函数的调用都是`unsafe`的，因为 Rust 编译器无法检查其他语言的操作。

从 Rust 1.29.2 开始，标准库定义了以下 unsafe trait（还有其他 trait，但还没有稳定下来，有些可能永远不会稳定下来）：

-   [`Send`] 是一个标记 trait（一个没有 API 的 trait），用于保证实现了[`Send`]的类型可以安全地发送（移动）到另一个线程。
-   [`Sync`] 是一个标记 trait，用于保证线程间可以通过共享引用安全地共享实现了[`Sync`]的类型。
-   [`GlobalAlloc`]允许自定义整个程序的内存分配器。

Rust 标准库也有很多地方在内部使用了 Unsafe Rust。这些实现一般都经过严格的人工检查，所以建立在这些实现之上的 Safe Rust 接口可以被认为是安全的。

之所以要像这样分离 Safe 和 Unsafe，归根到底在于 Safe Rust 的一个根本属性，即*可靠性*。

**无论怎样，Safe Rust 都不能导致未定义行为。**

Safe 与 Unsafe 分离的设计意味着 Safe Rust 和 Unsafe Rust 之间存在着不对等的信任关系。一方面， Safe Rust 本质上必须相信它所接触的任何 Unsafe Rust 都是正确编写的。另一方面，Unsafe Rust 在信任 Safe Rust 时必须非常小心。

例如，Rust 有[`PartialOrd`]和[`Ord`] trait 来区分“偏序”比较的类型和“全序”比较的类型（前者仅能进行比较而未必得出大小关系，而后者意味着每一个比较都有合理的结果）。

[`BTreeMap`]以没有定义全序关系的类型作为 key 是没有意义的，因此它要求其 key 实现`Ord`。然而，`BTreeMap`的实现中包含了 Unsafe 的代码。由于（用 Safe 代码就能写出的）不靠谱的`Ord`实现导致未定义行为是不可接受的，因此，BTreeMap 中的 Unsafe 代码必须健壮到这个地步：对于实际上并非全序关系的`Ord`实现也不会导致未定义行为——尽管我们指定`Ord`约束就是为了得到全序关系。

Unsafe Rust 代码不能信任 Safe Rust 代码逻辑无误。话虽如此，如果你输入的值，其类型并没有全序关系，`BTreeMap`仍然会变得乱七八糟。上一段只是说明它不会导致未定义行为。

有人可能会问，如果`BTreeMap`不能基于“它是 Safe 代码编写的”这一理由而信任`Ord`，那还有*什么* Safe 代码是能信任的呢？例如，`BTreeMap`依赖于整数和切片的正确实现。这些也是 Safe Rust 编写的，不是么？

区别在于范围的不同。当`BTreeMap`依赖于整数和切片时，它依赖于一个完全特定的实现。这里的风险经过评估可以与收益相权衡。在这个特定场景下，风险基本为零；如果整数和切片出了问题，*什么东西*都会出问题，因此不可能被忽视。而且，它们和`BTreeMap`是由同一批人维护的，所以很容易对它们进行监控。

另一方面，`BTreeMap`的 key 类型是泛型的。信任它的`Ord`实现意味着信任过去、现在和未来的每一个`Ord`实现。这里的风险很高：总有人会犯错误，把`Ord`实现坏，甚至直接谎称提供了一个全序关系，因为“这个实现看上去够用”。对于这种情况，`BTreeMap`需要有备无患。

同样的逻辑也适用于信任一个传递给你的闭包的行为是正确的。

问题是能否无限信任泛型类型参数？`unsafe` trait 应运而生。理论上，`BTreeMap`类型可以要求 key 实现一个新的 trait，称为`UnsafeOrd`，而不是`Ord`，它可能看起来像这样：

```rust
use std::cmp::Ordering;

unsafe trait UnsafeOrd {
    fn cmp(&self, other: &Self) -> Ordering;
}
```

然后，为一个类型实现`UnsafeOrd`就要带上`unsafe`前缀，表明开发者已经确保他们的实现遵循了该 trait 所预期的任何约束。在这种情况下，`BTreeMap`内部的 Unsafe Rust 有理由相信 key 类型的`UnsafeOrd`实现是正确的。否则错就在 unsafe trait 的实现，这与 Rust 的安全保证是一致的。

是否将 trait 标记为`unsafe`是 API 设计取舍的问题。Safe trait 实现起来更轻松，但任何依赖它的 Unsafe 代码面临不正确的实现也不能引发未定义行为。将 trait 标记为`unsafe`会将这个责任转移到实现者身上。按照 Rust 传统，往往避免将 trait 标记为`unsafe`，否则 Unsafe Rust 会无处不在，我们并不想看到这个结果。

`Send`和`Sync`被标记为 unsafe，是因为线程安全是一个*根本的属性*，要像应对一个有缺陷的`Ord`实现一样应对线程安全问题，对 unsafe 代码来说是不可能的。同理，`GlobalAlloc`被用于管理程序中所有的内存分配，诸如`Box`或`Vec`都建立在它的基础上。如果`GlobalAlloc`不正常了（例如把一块还被占用着的内存返回给了另一个请求），是绝无可能靠检测来补救的。

是否将你自己的 trait 标记为`unsafe`，也要基于类似的考虑做出决定。如果`unsafe`代码无法有效应对 trait 的错误实现，那么将 trait 标记为`unsafe`合情合理。

顺便一提，虽然`Send`和`Sync`是`unsafe` trait，但是当类型系统可以证明派生`Send`/`Sync`安全时，它们*也会*被自动实现。每个字段类型都满足`Send`的类型会自动派生`Send`。每个字段类型都满足`Sync`的类型会自动派生`Sync`。通过这种方式，这两个 trait 扩散`unsafe`的影响被控制到最小。而对于内存分配器，没多少人会去*实现*它们（说起来，直接使用内存分配器的人都很少）。

上文展示了 Safe Rust 和 Unsafe Rust 之间的平衡。将两者分离的设计，目的是让使用 Safe Rust 尽可能符合工效，反过来在编写 Unsafe Rust 时则需要额外的努力和细心。本书的其余部分主要是讨论需要什么形式的细心，以及Unsafe Rust 必须遵循什么约束。

[`Send`]: https://doc.rust-lang.org/std/marker/trait.Send.html
[`Sync`]: https://doc.rust-lang.org/std/marker/trait.Sync.html
[`GlobalAlloc`]: https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html
[conversions]: conversions.html
[ptr_offset]: https://doc.rust-lang.org/std/primitive.pointer.html#method.offset
[get_unchecked]: https://doc.rust-lang.org/std/primitive.slice.html#method.get_unchecked
[transmute]: https://doc.rust-lang.org/std/mem/fn.transmute.html
[`PartialOrd`]: https://doc.rust-lang.org/std/cmp/trait.PartialOrd.html
[`Ord`]: https://doc.rust-lang.org/std/cmp/trait.Ord.html
[`BTreeMap`]: https://doc.rust-lang.org/std/collections/struct.BTreeMap.html
