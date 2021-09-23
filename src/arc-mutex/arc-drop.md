# 丢弃

我们现在需要一种方法来减少引用计数，并在计数足够低时丢弃数据，否则数据将永远存在于堆中。

为了做到这一点，我们可以实现`Drop`。

我们大致需要：

1. 递减引用计数
2. 如果数据只剩下一个引用，那么：
3. 原子化地对数据进行屏障，以防止对数据的使用和删除进行重新排序
4. 丢弃内部数据

首先，我们需要获得对`ArcInner`的访问：

<!-- ignore: simplified code -->
```rust,ignore
let inner = unsafe { self.ptr.as_ref() };
```

现在，我们需要递减引用计数。为了简化我们的代码，如果从`fetch_sub`返回的值（递减引用计数之前的值）不等于`1`，我们可以直接返回（我们不是数据的最后一个引用）。

<!-- ignore: simplified code -->
```rust,ignore
if inner.rc.fetch_sub(1, Ordering::Relaxed) != 1 {
    return;
}
```

然后我们需要创建一个原子屏障来防止重新排序使用数据和删除数据。正如[标准库对`Arc`的实现][3]中所述。
> 需要这个内存屏障来防止数据使用的重新排序和数据的删除。因为它被标记为“Release”，引用计数的减少与“Acquire”屏障同步。这意味着数据的使用发生在减少引用计数之前，而减少引用计数发生在这个屏障之前，而屏障发生在数据的删除之前。（译者注：use < decrease < 屏障 < delete）
>
> 正如[Boost 文档][1]中所解释的那样。
>
> > 强制要求一个线程中对该对象的任何可能的访问（通过现有的引用）*发生在不同线程中删除该对象之前*是很重要的。这可以通过在丢弃一个引用后的“Release”操作来实现（任何通过该引用对对象的访问显然必须在之前发生），以及在删除对象前的“Acquire”操作。
>
> 特别是，虽然 Arc 的内容通常是不可改变的，但有可能对类似`Mutex<T>`的东西进行内部可变。由于`Mutex`在被删除时不会被获取，我们不能依靠它的同步逻辑来使线程 A 的写操作对线程 B 的析构器可见。
>
> 还要注意的是，这里的 Acquire fence 可能可以用 Acquire load 来代替，这可以在高度竞争的情况下提高性能。
> 参见[2]。
>
> [1]: https://www.boost.org/doc/libs/1_55_0/doc/html/atomic/usage_examples.html
> [2]: https://github.com/rust-lang/rust/pull/41714
[3]: https://github.com/rust-lang/rust/blob/e1884a8e3c3e813aada8254edfa120e85bf5ffca/library/alloc/src/sync.rs#L1440-L1467

为了做到这一点，我们可以这么做：

```rust
# use std::sync::atomic::Ordering;
use std::sync::atomic;
atomic::fence(Ordering::Acquire);
```

最后，我们可以 drop 数据本身。我们使用`Box::from_raw`来丢弃 Box 中的`ArcInner<T>`和它的数据。这需要一个`*mut T`而不是`NonNull<T>`，所以我们必须使用`NonNull::as_ptr`进行转换。

<!-- ignore: simplified code -->
```rust,ignore
unsafe { Box::from_raw(self.ptr.as_ptr()); }
```

这是安全的，因为我们知道我们拥有的是最后一个指向`ArcInner`的指针，而且其指针是有效的。

现在，让我们在`Drop`的实现中把这一切整合起来。

<!-- ignore: simplified code -->
```rust,ignore
impl<T> Drop for Arc<T> {
    fn drop(&mut self) {
        let inner = unsafe { self.ptr.as_ref() };
        if inner.rc.fetch_sub(1, Ordering::Release) != 1 {
            return;
        }
        // This fence is needed to prevent reordering of the use and deletion
        // of the data.
        atomic::fence(Ordering::Acquire);
        // This is safe as we know we have the last pointer to the `ArcInner`
        // and that its pointer is valid.
        unsafe { Box::from_raw(self.ptr.as_ptr()); }
    }
}
```
