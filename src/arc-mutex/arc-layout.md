# 布局

让我们开始为我们的`Arc`的实现做布局。

一个`Arc<T>`为`T`类型的值提供了线程安全的共享所有权，并在堆中分配。在 Rust 中，共享意味着不变性，所以我们不需要设计任何东西来管理对该值的访问，对吧？虽然像 Mutex 这样的内部可变性类型允许 Arc 的用户创建共享可变性，但 Arc 本身并不需要关注这些问题。

然而，有一个地方 Arc 需要关注可变：销毁。当 Arc 的所有所有者都销毁时，我们需要能够`drop`其内容并释放其分配。所以我们需要一种方法让所有者知道它是否是最后一个所有者，而最简单的方法就是对所有者进行计数——引用计数。

不幸的是，这种引用计数本质上是共享的可变状态，所以 Arc _需要_ 考虑同步问题。我们可以为此使用 Mutex，但那太过于杀鸡用牛刀了。相反，我们将使用 atomics。既然每个人都需要一个指向 T 的分配的指针，我们也可以把引用计数放在同一个分配中。

直观地说，它看起来就像这样：

```rust
use std::sync::atomic;

pub struct Arc<T> {
    ptr: *mut ArcInner<T>,
}

pub struct ArcInner<T> {
    rc: atomic::AtomicUsize,
    data: T,
}
```

这可以编译通过，然而它是不正确的。首先，编译器会给我们太严格的可变性。例如，在期望使用`Arc<&'a str>`的地方不能使用`Arc<&'static str>`。更重要的是，它将给 drop checker 提供不正确的所有权信息，因为它将假定我们不拥有任何`T`类型的值。由于这是一个提供值的共享所有权的结构，在某些时候会有一个完全拥有其数据的结构实例。参见[关于所有权和生命周期的章节](../ownership.md)，了解关于变异和 drop checker 的所有细节。

为了解决第一个问题，我们可以使用`NonNull<T>`。请注意，`NonNull<T>`是一个围绕原始指针的包装，并声明以下内容：

* 我们是`T`的协变
* 我们的指针从不为空

为了解决第二个问题，我们可以包含一个包含`ArcInner<T>`的`PhantomData`标记。这将告诉 drop checker，我们对`ArcInner<T>`（它本身包含`T`）的值有一些所有权的概念。

通过这些改变，我们得到了最终的结构：

```rust
use std::marker::PhantomData;
use std::ptr::NonNull;
use std::sync::atomic::AtomicUsize;

pub struct Arc<T> {
    ptr: NonNull<ArcInner<T>>,
    phantom: PhantomData<ArcInner<T>>,
}

pub struct ArcInner<T> {
    rc: AtomicUsize,
    data: T,
}
```
