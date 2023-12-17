# 布局

首先，我们需要想出结构布局。一个 Vec 有三个部分：一个指向分配的指针，分配的大小，以及已经初始化的元素数量。

直观来说，这意味着我们只需要这样的设计：

<!-- ignore: simplified code -->
```rust,ignore
pub struct Vec<T> {
    ptr: *mut T,
    cap: usize,
    len: usize,
}
```

这确实可以编译成功。但是不幸的是，这有些过于严格了。编译器会给我们太严格的可变性（variance）。比如一个`&Vec<&'static str>`不能用在预期`&Vec<&'a str>`的地方。参见[所有权和生命周期一章][ownership]中关于可变和 drop checker 的所有细节。

正如我们在所有权一章中看到的，当标准库拥有一个分配对象的原始指针时，它使用`Unique<T>`来代替`*mut T`。Unique 是不稳定的，所以如果可能的话，我们希望不要使用它。

简而言之，Unique 是一个原始指针的包装，并声明以下内容：

* 我们对`T`是协变的
* 我们可以拥有一个`T`类型的值（这和我们在这的例子无关，但是可以参考[`PhantonData`][phantom-data]那章来看看为什么真正的`std::vec::Vec<T>`需要这个）
* 如果`T`是`Send/Sync`，我们就是`Send/Sync`。
* 我们的指针从不为空（所以`Option<Vec<T>>`是空指针优化的）

我们可以在稳定的 Rust 中实现上述所有的要求。为此，我们不使用`Unique<T>`，而是使用[`NonNull<T>`][NonNull]，这是对原始指针的另一种包装，它为我们提供了上述的两个属性，即它在`T`上是协变的，并且被声明为永不为空。通过在`T`是`Send/Sync`的情况下实现`Send/Sync`，我们得到与使用`Unique<T>`相同的结果：

```rust
use std::ptr::NonNull;

pub struct Vec<T> {
    ptr: NonNull<T>,
    cap: usize,
    len: usize,
}

unsafe impl<T: Send> Send for Vec<T> {}
unsafe impl<T: Sync> Sync for Vec<T> {}
# fn main() {}
```

[ownership]: ../ownership.html
[phantom-data]: ../phantom-data.md
[NonNull]: https://doc.rust-lang.org/std/ptr/struct.NonNull.html
