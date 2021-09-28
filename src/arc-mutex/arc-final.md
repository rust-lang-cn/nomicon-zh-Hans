# 最终代码

这就是我们的最终代码，我在这里加了一些额外的注释并排序了一下 imports：

```rust
use std::marker::PhantomData;
use std::ops::Deref;
use std::ptr::NonNull;
use std::sync::atomic::{self, AtomicUsize, Ordering};

pub struct Arc<T> {
    ptr: NonNull<ArcInner<T>>,
    phantom: PhantomData<ArcInner<T>>,
}

pub struct ArcInner<T> {
    rc: AtomicUsize,
    data: T,
}

impl<T> Arc<T> {
    pub fn new(data: T) -> Arc<T> {
        // 当前的指针就是第一个引用，因此初始时设置 count=1
        let boxed = Box::new(ArcInner {
            rc: AtomicUsize::new(1),
            data,
        });
        Arc {
            // 我们从 Box::into_raw 得到该指针，因此使用 `.unwrap()` 是完全OK的 
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

impl<T> Clone for Arc<T> {
    fn clone(&self) -> Arc<T> {
        let inner = unsafe { self.ptr.as_ref() };
        // 我们没有修改 Arc 中的数据，因此在这里不需要任何原子的同步操作
        // 使用 relax 这种排序方式也就完全可行.
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

impl<T> Drop for Arc<T> {
    fn drop(&mut self) {
        let inner = unsafe { self.ptr.as_ref() };
        if inner.rc.fetch_sub(1, Ordering::Release) != 1 {
            return;
        }
        // 我们需要防止针对 inner 的使用和删除的重排序
        // 因此使用 fence 来进行保护是非常有必要.
        atomic::fence(Ordering::Acquire);

        // Safety: 我们知道这是最后一个对 ArcInner 的引用，并且这个指针是有效的
        unsafe { Box::from_raw(self.ptr.as_ptr()); }
    }
}
```
