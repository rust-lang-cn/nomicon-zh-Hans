# 幽灵数据

在处理不安全代码时，我们经常会遇到这样的情况：类型或生命周期在逻辑上与结构相关，但实际上并不是字段的一部分。这种情况最常发生在生命周期上。例如，`&'a [T]`的`Iter`（大约）定义如下：

```rust,compile_fail
struct Iter<'a, T: 'a> {
    ptr: *const T,
    end: *const T,
}
```

但是由于`'a`在结构体中是未使用的，所以它是*无约束*的。[由于这在历史上造成的麻烦][unused-param]，在结构定义中，不受约束的生命周期和类型是*禁止*的，因此我们必须在主体中以某种方式引用这些类型，正确地做到这一点对于正确的变异性和丢弃检查是必要的。

[unused-param]: https://rust-lang.github.io/rfcs/0738-variance.html#the-corner-case-unused-parameters-and-parameters-that-are-only-used-unsafely

我们使用`PhantomData`来做这个，它是一个特殊的标记类型。`PhantomData`不消耗空间，但为了静态分析的目的，模拟了一个给定类型的字段。这被认为比明确告诉类型系统你想要的变量类型更不容易出错，同时也提供了其他有用的东西，例如 auto traits 和 drop check 需要的信息。

Iter 逻辑上包含一堆`&'a T`，所以这正是我们告诉`PhantomData`要模拟的。

```rust
use std::marker;

struct Iter<'a, T: 'a> {
    ptr: *const T,
    end: *const T,
    _marker: marker::PhantomData<&'a T>,
}
```

就是这样，生命周期将被限定，而你的迭代器将在`'a`和`T`上进行协变。所有的东西都是有效的。

# 泛型参数和 drop 检查

在过去，曾经有另一个事情是需要仔细思考的，这篇文档曾经这么说：

> 另一个重要的例子是 Vec，它（大约）定义如下：
>
> ```rust
> struct Vec<T> {
>     data: *const T, // `*const`是可变异的！
>     len: usize,
>     cap: usize,
> }
> ```
>
> 与前面的例子不同的是，*看起来*一切都和我们想的一样。Vec 的每个通用参数至少在一个字段中出现。很好，可以开始了!
>
> 不对，不是这样。
>
> 丢弃检查器将慷慨地确定`Vec<T>`不拥有任何 T 类型的值。这将反过来使它得出结论，它不需要担心 Vec 在其析构器中丢弃任何 T 来确定丢弃检查的合理性。这将反过来允许人们使用 Vec 的析构器来制造不健壮性。
>
> 为了告诉 dropck 我们确实拥有 T 类型的值，因此在*我们*丢弃时可能会丢弃一些 T，我们必须添加一个额外的`PhantomData`，正如这样：
>
> ```rust
> use std::marker;
>
> struct Vec<T> {
>     data: *const T, // `*const`是可变异的！
>     len: usize,
>     cap: usize,
>     _marker: marker::PhantomData<T>,
> }
> ```

但自从[RFC 1238](https://rust-lang.github.io/rfcs/1238-nonparametric-dropck.html)之后，这就不正确也并不需要了。

如果你这么写：

```rust
struct Vec<T> {
    data: *const T, // `*const`是可变异的！
    len: usize,
    cap: usize,
}
# #[cfg(any())]
impl<T> Drop for Vec<T> { /* … */ }
```

那么`impl<T> Drop for Vec<T>`这条语句会让 Rust 知道`Vec<T>`_拥有_`T`类型的值（更准确地说：可能会在`Drop`实现中使用`T`类型的值），那么当`Vec<T>`被 drop 的时候，Rust 就不会允许它们 _悬垂_。

当一个类型已经有了 `Drop impl` 时，**添加一个额外的 `_owns_T: PhantomData<T>` 字段是多余的，而且没有任何效果**，从 dropck（Drop 检查）的角度来看（它仍然会影响变量和自动特征）。

- （高级边缘情况：如果包含 `PhantomData` 的类型根本没有 `Drop` 实现，但仍然有 drop glue（通过拥有另一个带有 drop glue 的字段），那么这里提到的 dropck/`#[may_dangle]` 规则也同样适用：一个 `PhantomData<T>` 字段将要求 `T` 在包含类型作用域结束时可被丢弃）。

---

但是这在某些场景下，会导致过于严格，这也是为啥标准库使用了一个不稳定并且`unsafe`的属性来切换回旧的`unchecked`的 drop 检查行为，也是接下来这个文档所警告的：`#[may_dangle]`属性。

### 一个例外：标准库的特殊情况及不稳定的`#[may_dangle]`

如果你只是写自己的库代码，那你可以跳过这章；但是如果你想知道标准库中真正的`Vec`是怎么实现的，你会发现它仍然需要`_owns_T: PhantomData<T>`字段来保证可靠性。

<details><summary>点这里查看原因</summary>

思考以下这个例子：

```rust
fn main() {
    let mut v: Vec<&str> = Vec::new();
    let s: String = "Short-lived".into();
    v.push(&s);
    drop(s);
} // <- `v`在这里被 drop 了
```

对于一个经典的`impl<T> Drop for Vec<T> {`定义，上面这段代码[会被编译器拒绝]。

[会被编译器拒绝]: https://rust.godbolt.org/z/ans15Kqz3

实际上，在这个例子中，我们的`Vec`的类型实际上是`Vec</* T = */ &'s str>`，是一个元素为`'s`生命周期的`str`ing 的 `Vec`，但是由于上面还有一行定义`let s: String`，它在`Vec` drop 之前就被 drop 了，所以在`Vec`被 drop 的时候，`'s`已经不再有效了，这时候`Drop`的实际签名为：`impl<'s> Drop for Vec<&'s str> {`。

这意味着，`Drop`被调用时，它将会面对一个无效的，或者说悬垂（dangling）的生命周期`'s`。这是违背了 Rust 原则的，Rust 原则要求所有的函数中的 Rust 引用都必须有效，解引用操作必须是合法的。

这也是为什么 Rust 会保守地拒绝这段代码。

然而，在真正的`Vec`中，`Drop`的实现并不关心`&'s str`，毕竟它（译者注：`&'s str`）没有自己的`Drop`实现（_since it has no drop glue of its own_），它想做的只是把它自己的 buffer 给释放掉。

换句话说，如果上述这个片段能被 Rust 接受那就再好不过了，我们通过封装`Vec`，或者说可以依赖于`Vec`一些特殊的属性：`Vec`可以承诺当它被 drop 时不会使用它拥有的`&'s str`。

这是一种`unsafe`的承诺，可以通过`#[may_dangle]`来表达：

```rust ,ignore
unsafe impl<#[may_dangle] 's> Drop for Vec<&'s str> { /* … */ }
```

或者，更通用化的：

```rust ,ignore
unsafe impl<#[may_dangle] T> Drop for Vec<T> { /* … */ }
```

这就是一个`unsafe`的方法用来摆脱 Rust drop 检查器这个保守的假设——一个 drop 的实例的类型参数不允许是悬垂的。

并且当这样做时，例如在标准库中，我们需要小心`T`有自己的`Drop`实现。比如，在这种情况下，想象用`struct PrintOnDrop<'s> /* = */ (&'s str);`替换`&'s str`，这将具有`Drop` impl，其内部的`&'s str`将被解引用并打印到屏幕上。

实际上，`Drop for Vec<T> {`，在释放自己的 Buffer 之前，确实必须在每个`T`类型的元素具有自定义`Drop`实现时递归地删除它；在 `PrintOnDrop<'s>`的情况下，这意味着`Vec<PrintOnDrop<'s>>`的`Drop`必须在释放 Buffer 之前递归地删除`PrintOnDrop<'s>`的元素。

所以当我们说`'s` `#[may_dangle]` 时，这是一个过于宽松的说法。我们更期望这么说说：“`'s`可能会悬垂，前提是它不涉及一些`Drop`自定义实现”。或者，更一般地说，“`T`可能会悬空，前提是它不涉及某些`Drop`自定义实现”。每当**我们拥有一个`T`**时，这种“例外的例外”是一种普遍的情况。这就是为什么 Rust 的`#[may_dangle]`足够聪明，_当泛型参数以拥有的方式_ 被 struct 的某个字段所保存时，会被禁用。（原文：That's why Rust's `#[may_dangle]` is smart enough to know of this opt-out, and will thus be disabled _when the generic parameter is held
in an owned fashion_ by the fields of the struct.）

这就是为什么最终标准库是这么写的：

```rust
# #[cfg(any())]
// 我们拉勾说好，当 drop `Vec`的时候不去用`T`
unsafe impl<#[may_dangle] T> Drop for Vec<T> {
    fn drop(&mut self) {
        unsafe {
            if mem::needs_drop::<T>() {
                /* … 除了这里，也就是说，… */
                ptr::drop_in_place::<[T]>(/* … */);
            }
            // …
            dealloc(/* … */)
            // …
        }
    }
}

struct Vec<T> {
    // … 除非事实上`Vec`拥有了`T`类型的元素，并且可能在 drop 时 drop 它们
    _owns_T: core::marker::PhantomData<T>,
    ptr: *const T, // `*const`是可变异的（但这本身并不能表达对`T`的所有权）
    len: usize,
    cap: usize,
}
```

</details>

---

拥有内存分配的原始指针是如此普遍的模式，以至于标准库为自己整了一个名为`Unique<T>`的类型：

- 包装一个`*const T`，用于变异
- 包括一个`PhantomData<T>`
- 根据包含的 T 自动派生`Send`/`Sync`
- 空指针的优化，将指针标记为`NonZero`

## `PhantomData`模式表

下面是一个关于所有可以使用`PhantomData`的神奇方式的表格：
(covariant:协变，invariant:不变，contravariant:逆变)

| Phantom type                | variance of `'a` | variance of `T`   | `Send`/`Sync`<br/>(or lack thereof)       | dangling `'a` or `T` in drop glue<br/>(_e.g._, `#[may_dangle] Drop`) |
|-----------------------------|:----------------:|:-----------------:|:-----------------------------------------:|:------------------------------------------------:|
| `PhantomData<T>`            | -                | **cov**ariant     | inherited                                 | disallowed ("owns `T`")                          |
| `PhantomData<&'a T>`        | **cov**ariant    | **cov**ariant     | `Send + Sync`<br/>requires<br/>`T : Sync` | allowed                                          |
| `PhantomData<&'a mut T>`    | **cov**ariant    | **inv**ariant     | inherited                                 | allowed                                          |
| `PhantomData<*const T>`     | -                | **cov**ariant     | `!Send + !Sync`                           | allowed                                          |
| `PhantomData<*mut T>`       | -                | **inv**ariant     | `!Send + !Sync`                           | allowed                                          |
| `PhantomData<fn(T)>`        | -                | **contra**variant | `Send + Sync`                             | allowed                                          |
| `PhantomData<fn() -> T>`    | -                | **cov**ariant     | `Send + Sync`                             | allowed                                          |
| `PhantomData<fn(T) -> T>`   | -                | **inv**ariant     | `Send + Sync`                             | allowed                                          |
| `PhantomData<Cell<&'a ()>>` | **inv**ariant    | -                 | `Send + !Sync`                            | allowed                                          |

  - 注意: opt-out Unpin 自动特性需要专用的 [`PhantomPinned`] 类型。

[`PhantomPinned`]: https://doc.rust-lang.org/std/marker/struct.PhantomPinned.html
