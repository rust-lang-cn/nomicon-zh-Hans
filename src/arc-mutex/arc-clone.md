# 克隆

现在我们已经有了一些基本的代码，我们需要一种方法来克隆`Arc`。

我们大致需要：

1. 递增原子引用计数
2. 从内部指针构建一个新的`Arc`实例

首先，我们需要获得对`ArcInner`的访问。

<!-- ignore: simplified code -->
```rust,ignore
let inner = unsafe { self.ptr.as_ref() };
```

我们可以通过以下方式更新原子引用计数：

<!-- ignore: simplified code -->
```rust,ignore
let old_rc = inner.rc.fetch_add(1, Ordering::???);
```

但是我们在这里应该使用什么顺序？我们实际上没有任何代码在克隆时需要原子同步，因为我们在克隆时不修改内部值。因此，我们可以在这里使用 Relaxed 顺序，这意味着没有 happen-before 的关系，但却是原子性的。然而，当`Drop` Arc 时，我们需要在递减引用计数时进行原子同步。这在[关于`Arc`的`Drop`实现部分](arc-drop.md)中有更多描述。关于原子关系和 Relaxed ordering 的更多信息，请参见[atomics 部分](../atomics.md)。

因此，代码变成了这样：

<!-- ignore: simplified code -->
```rust,ignore
let old_rc = inner.rc.fetch_add(1, Ordering::Relaxed);
```

我们需要增加一个导入来使用`Ordering`。

```rust
use std::sync::atomic::Ordering;
```

然而，我们现在的这个实现有一个问题：如果有人决定`mem::forget`一堆 Arc 怎么办？到目前为止，我们所写的代码（以及将要写的代码）假设引用计数准确地描绘了内存中的 Arc 的数量，但在`mem::forget`的情况下，这是错误的。因此，当越来越多的 Arc 从这个 Arc 中克隆出来，而它们又没有被`Drop`和参考计数被递减时，我们就会溢出！这将导致释放后使用（use-after-free）。这是**非常糟糕的事情！**

为了处理这个问题，我们需要检查引用计数是否超过某个任意值（低于`usize::MAX`，因为我们把引用计数存储为`AtomicUsize`），并*做一些防御*。

标准库的实现决定，如果任何线程上的引用计数达到`isize::MAX`（大约是`usize::MAX`的一半），就直接中止程序（因为在正常代码中这是非常不可能的情况，如果它发生，程序可能是非常有问题的）。基于的假设是，不应该有大约 20 亿个线程（或者在一些 64 位机器上大约**9万亿**个）在同时增加引用计数。这就是我们要做的。

实现这种行为是非常简单的。

<!-- ignore: simplified code -->
```rust,ignore
if old_rc >= isize::MAX as usize {
    std::process::abort();
}
```

然后，我们需要返回一个新的`Arc`的实例。

<!-- ignore: simplified code -->
```rust,ignore
Self {
    ptr: self.ptr,
    phantom: PhantomData
}
```

现在，让我们把这一切包在`Clone`的实现中。

<!-- ignore: simplified code -->
```rust,ignore
use std::sync::atomic::Ordering;

impl<T> Clone for Arc<T> {
    fn clone(&self) -> Arc<T> {
        let inner = unsafe { self.ptr.as_ref() };
        // Using a relaxed ordering is alright here as we don't need any atomic
        // synchronization here as we're not modifying or accessing the inner
        // data.
        let old_rc = inner.rc.fetch_add(1, Ordering::Relaxed);

        if old_rc >= isize::MAX as usize {
            std::process::abort();
        }

        Self {
            ptr: self.ptr,
            phantom: PhantomData,
        }
    }
}
```
