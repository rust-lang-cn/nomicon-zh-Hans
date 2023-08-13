# Safe 和 Unsafe 如何交互

Safe Rust 和 Unsafe Rust 之间有什么关系？它们又是如何交互的？

Safe Rust 和 Unsafe Rust 之间的边界由`unsafe`关键字控制，`unsafe`是承接了它们之间交互的桥梁。这就是为什么我们可以说 Safe Rust 是一种安全的语言：所有不安全的部分都被限制在“unsafe”边界之内。如果你愿意，你甚至可以把`#![forbid(unsafe_code)]`扔进你的代码库，以静态地保证你只写安全的 Rust。

`unsafe`关键字有两个用途：声明编译器不会保证这些代码的安全性，以及声明程序员已经确保这些代码是安全的。

你可以用`unsafe`来表示在 _函数_ 和 _trait 声明_ 这些行为不一定安全。对于函数，`unsafe`意味着函数的用户必须仔细阅读该函数的文档，以确保他们在使用该函数时能满足函数能安全运行的条件。对于 trait 声明，`unsafe`意味着 trait 的实现者必须仔细阅读 trait 文档，以确保他们的实现遵循了 trait 所要求条件。

你可以在一个块上使用`unsafe`来声明在其中执行的所有不安全操作都经过了验证以保证操作的安全性。例如，当传递给[`slice::get_unchecked`][get_unchecked]的索引在边界内，这一行为就是安全的。

你可以在 trait 的实现上使用`unsafe`来声明该实现满足了 trait 的条件。例如，实现[`Send`]说明这个类型移动到另一个线程是真正安全的。

标准库中有许多 unsafe 的函数，包括：

-   [`slice::get_unchecked`][get_unchecked]，它不会检查传入索引的有效性，允许违反内存安全的规则。
-   [`mem::transmute`][transmute]将一些数据重新解释为给定的类型，绕过类型安全的规则（详见[conversions]）。
-   每一个指向一个 Sized 类型的原始指针都有一个[`offset`][ptr_offset]方法，如果传递的偏移量不在[“界内”][ptr_offset]，则该调用是未定义行为。
-   所有 FFI（外部函数接口 Foreign Function Interface）函数的调用都是`unsafe`的，因为 Rust 编译器无法检查其他语言的操作。

从 Rust 1.29.2 开始，标准库定义了以下 unsafe trait（还有其他 trait，但还没有稳定下来，有些可能永远不会稳定下来）：

-   [`Send`] 是一个标记 trait（一个没有 API 的 trait），承诺实现了[`Send`]的类型可以安全地发送（移动）到另一个线程。
-   [`Sync`] 是一个标记 trait，承诺线程可以通过共享引用安全地共享实现了[`Sync`]的类型。
-   [`GlobalAlloc`]允许自定义整个程序的内存分配器。

Rust 标准库的大部分内容也在内部使用了 Unsafe Rust。这些实现一般都经过严格的人工检查，所以建立在这些实现之上的 Safe Rust 接口可以被认为是安全的。

我们需要将它们分离，是因为 Safe Rust 的一个基本属性，即*健全性属性*。

**无论怎样，Safe Rust 都不会导致未定义行为。**

Safe 与 Unsafe 分离的设计意味着 Safe Rust 和 Unsafe Rust 之间存在着不对等的信任关系。一方面， Safe Rust 本质上必须相信它所接触的任何 Unsafe Rust 都是正确编写的。另一方面，Unsafe Rust 在信任 Safe Rust 时必须非常小心。

例如，Rust 有[`PartialOrd`]和[`Ord`] trait 来区分“部分序”比较的类型和“全序”比较的类型（这意味着比较行为必须是合理的）。

[`BTreeMap`]对于`PartialOrd`的类型来说并没有实际意义，因此它要求其 key 实现`Ord`。然而，`BTreeMap`在其实现中包含了 Unsafe 的代码，所以无法接受马虎的（可以用Safe编写的）`Ord`实现，因为这会导致未定义行为。因此，BTreeMap 中的 Unsafe 代码必须被编写成对实际上不完全的`Ord`实现具有鲁棒性——尽管我们要求`Ord`是正确实现的。

Unsafe Rust 代码不能相信 Safe Rust 代码会被正确编写。也就是说，如果你输入了没有正确实现全序排序的值，`BTreeMap`仍然会表现得完全不正常。它只是不会导致未定义行为。

有人可能会问，如果`BTreeMap`不能信任`Ord`，因为它是安全的，那么它为什么能信任*任何*安全的代码呢？例如，`BTreeMap`依赖于整数和 slice 的正确实现。这些也是安全的，对吗？

区别在于范围的不同。当`BTreeMap`依赖于整数和分片时，它依赖于一个非常具体的实现。这是一个可以衡量的风险，可以与收益相权衡。在这种情况下，风险基本上为零；如果整数和 slice 被破坏，那么*所有人*都会被破坏。而且，它们是由维护`BTreeMap`的人维护的，所以很容易对它们进行监控。

另一方面，`BTreeMap`的 key 类型是泛型的。信任它的`Ord`实现意味着信任过去、现在和未来的每一个`Ord`实现。这里的风险很高：有人会犯错误，把他们的`Ord`实现搞得一团糟，甚至直接撒谎说提供了一个完整的排序，因为“它看起来很有效”。`BTreeMap`需要做好准备应对这种情况的发生。

同样的逻辑也适用于信任一个传递给你的闭包会有正确的行为。

`unsafe` trait 就是用来解决泛型的信任问题。理论上，`BTreeMap`类型可以要求 key 实现一个新的 trait，称为`UnsafeOrd`，而不是`Ord`，它可能看起来像这样：

```rust
use std::cmp::Ordering;

unsafe trait UnsafeOrd {
    fn cmp(&self, other: &Self) -> Ordering;
}
```

然后，一个类型将使用`unsafe`来实现`UnsafeOrd`，表明他们已经确保他们的实现满足了该 trait 所期望的任何条件。在这种情况下，`BTreeMap`内部的 Unsafe Rust 有理由相信 key 类型的`UnsafeOrd`实现是正确的。如果不是这样，那就是 unsafe trait 实现的错，这与 Rust 的安全保证是一致的。

是否将一个 trait 标记为`unsafe`是一个 API 设计。一个 safe trait 更容易实现，但任何依赖它的 Unsafe 代码都必须抵御不正确的行为。将 trait 标记为`unsafe`会将这个责任转移到实现者身上。Rust 习惯于避免将 trait 标记为`unsafe`，因为它使 Unsafe Rust 普遍存在，这并不可取。

`Send`和`Sync`被标记为 unsafe，是因为线程安全是一个*基本*的属性，unsafe 代码不可能像抵御一个有缺陷的`Ord`实现那样去抵御它。同样地，`GlobalAllocator`是对程序中所有的内存进行记录，其他的东西如`Box`或`Vec`都建立在它的基础上。如果它做了一些奇怪的事情（当它还在使用的时候，把同一块内存给了另一个请求），就没有机会检测到并采取任何措施了。

决定是否将你自己的 trait 标记为“unsafe”，也是出于同样的考虑。如果“unsafe”的代码不能抵御 trait 的错误实现，那么将 trait 标记为“unsafe”就是一个合理的选择。

顺便说一下，虽然`Send`和`Sync`是`unsafe`的特性，但它们*也是*自动实现的类型，当这种派生可以证明是安全的。`Send`是自动派生的，只适用于一个类型下所有类型都实现了`Send`。`Sync`是自动派生的，只适用于一个类型下所有类型都实现了`Sync`。这最大限度地减少了使这两个 trait “unsafe” 的危险。而且，没有多少人会去*实现*内存分配器（或者针对这个问题而言，直接使用它们）。

这就是 Safe Rust 和 Unsafe Rust 之间的平衡。这种分离是为了使 Safe Rust 的使用尽可能符合人体工程学，但在编写 Unsafe Rust 时需要额外的努力和小心。本书的其余部分主要是讨论必须采取的谨慎，以及Unsafe Rust 必须坚持的契约。

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
