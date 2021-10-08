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

我们使用`PhantomData`来做这个，它是一个特殊的标记类型。`PhantomData`不消耗空间，但为了静态分析的目的，模拟了一个给定类型的字段。这被认为比明确告诉类型系统你想要的变量类型更不容易出错，同时也提供了其他有用的东西，例如 drop check 需要的信息。

Iter 逻辑上包含一堆`&'a T`，所以这正是我们告诉`PhantomData`要模拟的。

```rust
use std::marker;

struct Iter<'a, T: 'a> {
    ptr: *const T,
    end: *const T,
    _marker: marker::PhantomData<&'a T>,
}
```

就是这样，生命周期将被限定，而你的迭代器将在`'a`和`T`上进行变异。所有的东西都是有效的。

另一个重要的例子是 Vec，它（大约）定义如下：

```rust
struct Vec<T> {
    data: *const T, // *const 是可变异的！
    len: usize,
    cap: usize,
}
```

与前面的例子不同的是，*看起来*一切都和我们想的一样。Vec 的每个通用参数至少在一个字段中出现。很好，可以开始了!

不对，不是这样。

丢弃检查器将慷慨地确定`Vec<T>`不拥有任何 T 类型的值。这将反过来使它得出结论，它不需要担心 Vec 在其析构器中丢弃任何 T 来确定丢弃检查的合理性。这将反过来允许人们使用 Vec 的析构器来制造不健壮性。

为了告诉 dropck 我们确实拥有 T 类型的值，因此在*我们*丢弃时可能会丢弃一些 T，我们必须添加一个额外的`PhantomData`，正如这样：

```rust
use std::marker;

struct Vec<T> {
    data: *const T, // *const 是可变异的！
    len: usize,
    cap: usize,
    _marker: marker::PhantomData<T>,
}
```

拥有内存分配的原始指针是如此普遍的模式，以至于标准库为自己整了一个名为`Unique<T>`的类型：

* 包装一个`*const T`，用于变异
* 包括一个`PhantomData<T>`
* 根据包含的 T 自动派生`Send`/`Sync`
* 空指针的优化，将指针标记为`NonZero`

## `PhantomData`模式表

下面是一个关于所有可以使用`PhantomData`的神奇方式的表格：  
(covariant:协变，invariant:不变，contravariant:逆变)

| Phantom type                | `'a`      | `T`                       |
|-----------------------------|-----------|---------------------------|
| `PhantomData<T>`            | -         | covariant (with drop check) |
| `PhantomData<&'a T>`        | covariant | covariant                 |
| `PhantomData<&'a mut T>`    | covariant | invariant                 |
| `PhantomData<*const T>`     | -         | covariant                 |
| `PhantomData<*mut T>`       | -         | invariant                 |
| `PhantomData<fn(T)>`        | -         | contravariant             |
| `PhantomData<fn() -> T>`    | -         | covariant                 |
| `PhantomData<fn(T) -> T>`   | -         | invariant                 |
| `PhantomData<Cell<&'a ()>>` | invariant | -                         |
