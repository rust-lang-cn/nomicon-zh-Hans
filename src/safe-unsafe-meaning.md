# 安全和不安全如何交互

安全 Rust 和不安全 Rust 之间的关系是什么？它们如何交互？

Safe Rust 和 Unsafe Rust 之间的边界是由`unsafe`关键字控制的，它作为它们之间的接口。这就是为什么我们可以说 Safe Rust 是一种安全的语言：所有不安全的部分都被保留在“unsafe”边界之后。如果你愿意，你甚至可以把`#![forbid(unsafe_code)]`扔进你的代码库，以静态地保证你只写安全的 Rust。

`unsafe`关键字有两个用途：声明存在编译器无法检查的契约，以及声明程序员已经检查过这些契约的满足。

你可以用`unsafe`来表示在 _函数_ 和 _trait 声明_ 上存在未经检查的契约。在函数上，`unsafe`意味着函数的用户必须仔细阅读该函数的文档，以确保他们在使用该函数时能保持该函数所要求的契约。在 trait 声明中，`unsafe`意味着 trait 的实现者必须阅读 trait 文档，以确保他们的实现满足 trait 所要求的契约。

你可以在一个块上使用`unsafe`来声明在其中执行的所有不安全操作都要经过验证以满足这些操作的契约。例如，传递给[`slice::get_unchecked`][get_unchecked]的索引是界内的。

你可以在 trait 实现上使用`unsafe`来声明该实现维护了 trait 的契约。例如，一个实现[`Send`]的类型移动到另一个线程是真正安全的。

标准库中有许多不安全的函数，包括。

- [`slice::get_unchecked`][get_unchecked]，它执行未经检查的索引，允许随意地违反内存安全。
- [`mem::transmute`][transmute]将一些值重新解释为具有给定的类型，以任意的方式绕过类型安全（详见[conversions]）。
- 每一个指向一个大小类型的原始指针都有一个[`offset`][ptr_offset]方法，如果传递的偏移量不在[“界内”][ptr_offset]，则该调用是未定义行为。
- 所有 FFI（Foreign Function Interface）函数的调用都是`不安全`的，因为其他语言可以进行 Rust 编译器无法检查的任意操作。

从 Rust 1.29.2 开始，标准库定义了以下不安全特性（还有其他特性，但还没有稳定下来，有些可能永远不会稳定下来）：

- [`Send`] 是一个标记 trait（一个没有 API 的 trait），承诺实现者可以安全地发送（移动）到另一个线程。
- [`Sync`] 是一个标记特性，承诺线程可以通过共享引用安全地共享实现者。
- [`GlobalAlloc`]允许自定义整个程序的内存分配器。

Rust 标准库的大部分内容也在内部使用了 Unsafe Rust。这些实现一般都经过严格的人工检查，所以建立在这些实现之上的安全 Rust 接口可以被认为是安全的。

我们需要将它们分离，是因为安全 Rust 的一个基本属性，即*健全性属性*。

**无论怎样，安全 Rust 都不会导致未定义行为。**

安全/不安全分离的设计意味着安全 Rust 和不安全 Rust 之间存在着不对称的信任关系。安全 Rust 本质上必须相信它所接触的任何不安全 Rust 都是正确编写的。另一方面，不安全的 Rust 在信任安全 Rust 时必须非常小心。

例如，Rust 有[`PartialOrd`]和[`Ord`]特性来区分“只是”被比较的类型和提供“总”排序的类型（这意味着比较行为是合理的）。

[`BTreeMap`]对于`PartialOrd`的类型来说并没有实际意义，因此它要求其键实现`Ord`。然而，`BTreeMap`在其实现中包含了不安全的 Rust 代码。因为马虎的`Ord`实现（可以在安全 Rust 中编写）会导致未定义行为，这是不可接受的，BTreeMap 中的不安全代码必须被编写成对实际上不完全的`Ord`实现具有鲁棒性——尽管这正是要求`Ord`的全部意义。

不安全的 Rust 代码不能相信安全的 Rust 代码会被正确编写。也就是说，如果你输入了没有总排序的值，`BTreeMap`仍然会表现得完全不正常。它只是不会导致未定义行为。

有人可能会问，如果`BTreeMap`不能信任`Ord`，因为它是安全的，那么它为什么能信任*任何*安全的代码呢？例如，`BTreeMap`依赖于整数和 slice 的正确实现。这些也是安全的，对吗？

区别在于范围的不同。当`BTreeMap`依赖于整数和分片时，它依赖于一个非常具体的实现。这是一个可以衡量的风险，可以与收益相权衡。在这种情况下，风险基本上为零；如果整数和 slice 被破坏，那么*所有人*都会被破坏。而且，它们是由维护`BTreeMap`的人维护的，所以很容易对它们进行监控。

另一方面，`BTreeMap`的键类型是通用的。信任它的`Ord`实现意味着信任过去、现在和未来的每一个`Ord`实现。这里的风险很高：有人会犯错误，把他们的`Ord`实现搞得一团糟，甚至直接撒谎说提供了一个完整的排序，因为“它看起来很有效”。当这种情况发生时，`BTreeMap`需要做好准备。

同样的逻辑也适用于信任一个传递给你的闭包会有正确的行为。

这种无限制的泛型信任问题是`unsafe` trait 存在的问题。以解决这个问题，理论上，`BTreeMap`类型可以要求键实现一个新的 trait，称为`UnsafeOrd`，而不是`Ord`，它可能看起来像这样：

```rust
use std::cmp::Ordering;

unsafe trait UnsafeOrd {
    fn cmp(&self, other: &Self) -> Ordering;
}
```

然后，一个类型将使用`unsafe`来实现`UnsafeOrd`，表明他们已经确保他们的实现维护了该 trait 所期望的任何契约。在这种情况下，`BTreeMap`内部的 Unsafe Rust 有理由相信键类型的`UnsafeOrd`实现是正确的。如果不是这样，那就是不安全 trait 实现的错，这与 Rust 的安全保证是一致的。

决定是否将一个 trait 标记为“不安全”是一个 API 设计选择。一个安全的 trait 更容易实现，但任何依赖它的不安全代码都必须抵御不正确的行为。将 trait 标记为“不安全”会将这个责任转移到实现者身上。Rust 传统上避免将特性标记为“不安全”，因为它使不安全的 Rust 普遍存在，这并不可取。

`Send`和`Sync`被标记为不安全，因为线程安全是一个*基本*的属性，不安全的代码不可能像抵御一个有缺陷的`Ord`实现那样去抵御它。同样地，`GlobalAllocator`是对程序中所有的内存进行记录，其他的东西如`Box`或`Vec`都建立在它的基础上。如果它做了一些奇怪的事情（当它还在使用的时候，把同一块内存给了另一个请求），就没有机会检测到并采取任何措施了。

决定是否将你自己的特性标记为“不安全”，也是出于同样的考虑。如果“不安全”的代码不能合理地期望抵御 trait 被破坏的实现，那么将 trait 标记为“不安全”就是一个合理的选择。

顺便说一下，虽然`Send`和`Sync`是`不安全`的特性，但它们*也是*自动实现的类型，当这种派生可以证明是安全的。`Send`是自动派生的，只适用于由类型也实现了`Send`的值组成的所有类型。`Sync`是自动派生的，只适用于由类型也实现了`Sync`的值组成的所有类型。这最大限度地减少了使这两个特征“不安全”的普遍的不安全因素。而且，没有多少人会去*实现*内存分配器（或者针对这个问题而言，直接使用它们）。

这就是安全和不安全的 Rust 之间的平衡。这种分离是为了使安全 Rust 的使用尽可能符合人体工程学，但在编写不安全 Rust 时需要额外的努力和小心。本书的其余部分主要是讨论必须采取的那种谨慎，以及不安全的 Rust 必须坚持的契约。

[`send`]: https://doc.rust-lang.org/std/marker/trait.Send.html
[`sync`]: https://doc.rust-lang.org/std/marker/trait.Sync.html
[`globalalloc`]: https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html
[conversions]: conversions.html
[ptr_offset]: https://doc.rust-lang.org/std/primitive.pointer.html#method.offset
[get_unchecked]: https://doc.rust-lang.org/std/primitive.slice.html#method.get_unchecked
[transmute]: https://doc.rust-lang.org/std/mem/fn.transmute.html
[`partialord`]: https://doc.rust-lang.org/std/cmp/trait.PartialOrd.html
[`ord`]: https://doc.rust-lang.org/std/cmp/trait.Ord.html
[`btreemap`]: https://doc.rust-lang.org/std/collections/struct.BTreeMap.html
