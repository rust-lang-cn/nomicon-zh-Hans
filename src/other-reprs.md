# 可选的数据布局

Rust 允许你指定不同于默认的数据布局策略，并为你提供了[不安全代码指南](注意，它是**非**正式的)。

## repr(C)

这是最重要的“repr”。它的意图相当简单：做 C 所做的事。字段的顺序、大小和对齐方式与你在 C 或 C++ 中期望的完全一样。任何你期望通过 FFI 边界的类型都应该有`repr(C)`，因为 C 是编程世界的语言框架。这对于合理地使用数据布局做更多的技巧也是必要的，比如将值重新解释为不同的类型。

我们强烈建议使用[rust-bindgen]和/或[cbindgen]来为你管理 FFI 的边界。Rust 团队与这些项目紧密合作，以确保它们能够稳健地工作，并与当前和未来关于类型布局和 `repr`s 的保证兼容。

必须记住`repr(C)`与 Rust 更奇特的数据布局功能的互动。由于它具有“用于 FFI”和“用于布局控制”的双重目的，`repr(C)`可以应用于那些如果通过 FFI 边界就会变得无意义或有问题的类型：

- ZST 仍然是零大小，尽管这不是 C 语言的标准行为，而且明确违背了 C++ 中空类型的行为，即它们仍然应该消耗一个字节的空间
- DST 指针（宽指针）和 tuple 在 C 语言中没有对应的概念，因此从来不是 FFI 安全的
- 带有字段的枚举在 C 或 C++ 中也没有对应的概念，但是类型的有效桥接[是被定义的][really-tagged]
- 如果`T`是一个[FFI 安全的非空指针类型](ffi.html#空指针优化)，`Option<T>`被保证具有与`T`相同的布局和 ABI，因此也是 FFI 安全的。截至目前，这包括`&`、`&mut`和函数指针，所有这些都不能为空。
- 就`repr(C)`而言，元组结构和结构一样，因为与结构的唯一区别是字段没有命名。
- `repr(C)`相当于无字段枚举的`repr(u*)`之一（见下一节）。选择的大小是目标平台的 C 应用二进制接口（ABI）的默认枚举大小。请注意，C 语言中的枚举表示法是实现定义的，所以这实际上是一个“最佳猜测”。特别是，当对应的 C 代码在编译时带有某些标志时，这可能是不正确的。
- 带有`repr(C)`或`repr(u*)`的无字段枚举仍然不能在没有相应变量的情况下设置为整数值，尽管这在 C 或 C++ 中是允许的行为。如果（不安全地）构造一个枚举的实例，但不与它的一个变体相匹配，这是未定义的行为(这使得详尽的匹配可以继续被编写和编译为正常行为)。

## repr(transparent)

`#[repr(transparent)]`只能用于只有单个非零大小字段（可能还有其他零大小字段）的结构或者单变体 enum 中。其效果是，整个结构的布局和 ABI 被保证与该字段相同。

> 注意：有一个叫做`transparent_unions`的 nightly 的特性，可以让你对 union 指定`repr(transparent)`。不过由于设计上的一些顾虑，这个特性目前还未稳定，参考[issue-60405](issue-60405)。

我们的目标是使单一字段和结构/枚举之间的转换成为可能。一个例子是[`UnsafeCell`]，它可以被转换为它所包装的类型。（[`UnsafeCell`]也用了一个不稳定的特性[no_niche][no-niche-pull]，所以当它嵌套其它类型的时候，它的 ABI 也并没有一个稳定的保证。）

另外，当我们通过 FFI 传递结构/枚举，并且其中内部字段类型是另一端所需的类型时，我们能保证这是正确的。特别是，这对于`struct Foo(f32)`或者`enum Foo { Bar(f32) }`总是具有与`f32`相同的 ABI 是必要的。

只有在唯一的字段为`pub`或其内存布局在文档中所承诺的情况下，该 repr 才被视为一个类型的公共 ABI 的一部分。否则，该内存布局不应被其他 crate 所依赖。

更多细节可以参考[RFC 1758][rfc-transparent]和[RFC 2645][rfc-transparent-unions-enums]。

## repr(u*), repr(i*)

这些指定了使无字段枚举的大小。如果判别符超过了它可以容纳的整数，就会产生一个编译时错误。你可以通过将溢出的元素明确设置为 0 来手动要求 Rust 允许这样做。

术语“无字段枚举”仅意味着该枚举在其任何变体中都没有数据。没有`repr(u*)`或`repr(C)`的无字段枚举仍然是一个 Rust 本地类型，没有稳定的 ABI 表示。添加`repr`会使它在 ABI 上被视为与指定的整数大小完全相同。

如果枚举有字段，其效果类似于`repr(C)`的效果，因为该类型有一个定义的布局。这使得将枚举传递给 C 代码或者访问该类型的原始表示并直接操作其标记和字段成为可能，详见[RFC][really-tagged]。

这些“repr”对结构（struct）没有作用。

在含有字段的枚举中加入明确的`repr(u*)`、`repr(i*)`或`repr(C)`可以抑制空指针优化，比如：

```rust
# use std::mem::size_of;
enum MyOption<T> {
    Some(T),
    None,
}

#[repr(u8)]
enum MyReprOption<T> {
    Some(T),
    None,
}

assert_eq!(8, size_of::<MyOption<&u16>>());
assert_eq!(16, size_of::<MyReprOption<&u16>>());
```

空指针优化针对无字段且拥有`repr(u*)`、`repr(i*)`或`repr(C)`的枚举仍然生效。

## repr(packed)

`repr(packed)`强制 Rust 去掉任何填充，只将类型对齐到一个字节。这可能会改善内存占用，但可能会有其他负面的副作用。

特别是，大多数架构*强烈地*希望数值被对齐。这可能意味着不对齐的加载会受到惩罚（x86），甚至会出现故障（一些 ARM 芯片）。对于简单的情况，如直接加载或存储一个已打包的字段，编译器可能能够用移位和掩码来解决对齐问题。然而，如果你对一个已打包的字段进行引用，编译器就不太可能发出代码来避免无对齐的加载。

[由于这可能导致未定义的行为][ub loads]，我们在 Lint 中已经实现了对应的检查，并且该行为会被认为是错误。

`repr(packed)`是不能轻易使用的，除非你有极端的要求，否则不应该使用这个。

这个 repr 是对`repr(C)`和`repr(Rust)`的修改。

## repr(align(n))

`repr(align(n))`(其中`n`是 2 的幂)强制类型*至少*按照 n 对齐。

这可以实现一些技巧，比如确保数组中的相邻元素不会彼此共享同一个缓存行（这可能会加快某些类型的并发代码）。

这是`repr(C)`和`repr(Rust)`的一个修改版本，它与`repr(packed)`不兼容。

[不安全代码指南]: https://rust-lang.github.io/unsafe-code-guidelines/layout.html
[ub loads]: https://github.com/rust-lang/rust/issues/27060
[issue-60405]: https://github.com/rust-lang/rust/issues/60405
[`unsafecell`]: https://doc.rust-lang.org/std/cell/struct.UnsafeCell.html
[rfc-transparent]: https://github.com/rust-lang/rfcs/blob/master/text/1758-repr-transparent.md
[rfc-transparent-unions-enums]: https://rust-lang.github.io/rfcs/2645-transparent-unions.html
[really-tagged]: https://github.com/rust-lang/rfcs/blob/master/text/2195-really-tagged-unions.md
[rust-bindgen]: https://rust-lang.github.io/rust-bindgen/
[cbindgen]: https://github.com/eqrion/cbindgen
[no-niche-pull]: https://github.com/rust-lang/rust/pull/68491
