# 基本代码

现在我们已经确定了实现`Arc`的布局，让我们开始写一些基本代码。

## 构建 Arc

我们首先需要一种方法来构造一个`Arc<T>`。

这很简单，因为我们只需要把`ArcInner<T>`扔到一个 Box 里并得到一个`NonNull<T>`的指针。

<!-- ignore: simplified code -->

```rust,ignore
impl<T> Arc<T> {
    pub fn new(data: T) -> Arc<T> {
        // 当前的指针就是第一个引用，因此初始时设置 count 为 1
        let boxed = Box::new(ArcInner {
            rc: AtomicUsize::new(1),
            data,
        });
        Arc {
            // 我们从 Box::into_raw 得到该指针，因此使用 `.unwrap()` 是完全可行的
            ptr: NonNull::new(Box::into_raw(boxed)).unwrap(),
            phantom: PhantomData,
        }
    }
}
```

## Send 和 Sync

由于我们正在构建并发原语，因此我们需要能够跨线程发送它。因此，我们可以实现`Send`和`Sync`标记特性。有关这些的更多信息，请参阅[有关`Send`和`Sync`的部分](../send-and-sync.md)。

这是没问题的，因为：

- 当且仅当你拥有唯一的 Arc 引用时，你才能获得其引用数据的可变引用（这仅发生在`Drop`中）
- 我们使用原子操作进行共享可变引用计数

<!-- ignore: simplified code -->

```rust,ignore
unsafe impl<T: Sync + Send> Send for Arc<T> {}
unsafe impl<T: Sync + Send> Sync for Arc<T> {}
```

我们需要约束`T: Sync + Send`，因为如果我们不提供这些约束，就有可能通过`Arc`跨越线程边界共享不安全的值，这有可能导致数据竞争或不可靠。

例如，如果没有这些约束，`Arc<Rc<u32>>`将是`Sync + Send`，这意味着你可以从`Arc`中克隆出`Rc`来跨线程发送（不需要创建一个全新的`Rc`），这将产生数据竞争，因为`Rc`不是线程安全的.

## 获取`ArcInner`

为了将`NonNull<T>`指针解引用为`T`，我们可以调用`NonNull::as_ref`。这是不安全的，与普通的`as_ref`函数不同，所以我们必须这样调用它。

<!-- ignore: simplified code -->
```rust,ignore
unsafe { self.ptr.as_ref() }
```

在这段代码中，我们将多次使用这个片段（通常与相关的`let`绑定）。

这种不安全是没问题的，因为当这个`Arc`存活的时候，我们可以保证内部指针是有效的。

## Deref

好了。现在我们可以制作`Arc`了（很快就能正确地克隆和销毁它们），但是我们怎样才能获得里面的数据呢？

我们现在需要的是一个`Deref`的实现。

我们需要导入该 Trait：

<!-- ignore: simplified code -->

```rust,ignore
use std::ops::Deref;
```

这里是实现：

<!-- ignore: simplified code -->

```rust,ignore
impl<T> Deref for Arc<T> {
    type Target = T;

    fn deref(&self) -> &T {
        let inner = unsafe { self.ptr.as_ref() };
        &inner.data
    }
}
```

看着很简单，对不？这只是解除了对`ArcInner<T>`的`NonNull`指针的引用，然后得到了对里面数据的引用。

## 代码

下面是本节的所有代码。

<!-- ignore: simplified code -->

```rust,ignore
use std::ops::Deref;

impl<T> Arc<T> {
    pub fn new(data: T) -> Arc<T> {
        // 当前的指针就是第一个引用，因此初始时设置 count 为 1
        let boxed = Box::new(ArcInner {
            rc: AtomicUsize::new(1),
            data,
        });
        Arc {
            // 我们从 Box::into_raw 得到该指针，因此使用 `.unwrap()` 是完全可行的
            ptr: NonNull::new(Box::into_raw(boxed)).unwrap(),
            phantom: PhantomData,
        }
    }
}

unsafe impl<T: Sync + Send> Send for Arc<T> {}
unsafe impl<T: Sync + Send> Sync for Arc<T> {}


impl<T> Deref for Arc<T> {
    type Target = T;

    fn deref(&self) -> &T {
        let inner = unsafe { self.ptr.as_ref() };
        &inner.data
    }
}
```
