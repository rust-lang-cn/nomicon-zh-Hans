# 强转

在某些情况下，类型可以隐式地被强转。这些变化通常只是*削弱*类型，主要集中在指针和生命周期方面。它们的存在主要是为了让 Rust 在更多的情况下“正常工作”，而且基本上是无害的。

关于所有强转类型的详尽列表，请参见《The Reference》中的[Coercion types]部分。

请注意，在匹配 Trait 时，我们不进行强制转换（除了接收者，见[下一页][dot-operator]）。如果某个类型`U`有一个`impl`，而`T`可以强转到`U`，这并不构成`T`的实现。例如，下面的内容不会通过类型检查，尽管将`t`强转到`&T`是可以的，并且有针对`&T`的`impl`。

```rust,compile_fail
trait Trait {}

fn foo<X: Trait>(t: X) {}

impl<'a> Trait for &'a i32 {}

fn main() {
    let t: &mut i32 = &mut 0;
    foo(t);
}
```

这样编译失败：

```text
error[E0277]: the trait bound `&mut i32: Trait` is not satisfied
 --> src/main.rs:9:9
  |
3 | fn foo<X: Trait>(t: X) {}
  |           ----- required by this bound in `foo`
...
9 |     foo(t);
  |         ^ the trait `Trait` is not implemented for `&mut i32`
  |
  = help: the following implementations were found:
            <&'a i32 as Trait>
  = note: `Trait` is implemented for `&i32`, but not for `&mut i32`
```

[Coercion types]: https://doc.rust-lang.org/reference/type-coercions.html#coercion-types
[dot-operator]: ./dot-operator.html
