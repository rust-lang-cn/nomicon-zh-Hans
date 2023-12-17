# RawVec

我们实际上在这里达到了一个有趣的状态：我们在 Vec 和 IntoIter 中重复了指定缓冲区和释放其内存的逻辑。现在我们已经实现了它，并且确定了*实际的*逻辑重复，这是一个进行一些逻辑压缩的好时机。

我们将抽象出`(ptr, cap)`对，并为它们编写分配、增长和释放的逻辑：

<!-- ignore: simplified code -->

```rust,ignore
struct RawVec<T> {
    ptr: NonNull<T>,
    cap: usize,
}

unsafe impl<T: Send> Send for RawVec<T> {}
unsafe impl<T: Sync> Sync for RawVec<T> {}

impl<T> RawVec<T> {
    fn new() -> Self {
        assert!(mem::size_of::<T>() != 0, "TODO: implement ZST support");
        RawVec {
            ptr: NonNull::dangling(),
            cap: 0,
        }
    }

    fn grow(&mut self) {
        // 保证新申请的内存没有超出 `isize::MAX` 字节
        let new_cap = if self.cap == 0 { 1 } else { 2 * self.cap };

        // `Layout::array` 会检查申请的空间是否小于等于 usize::MAX，
        // 但是因为 old_layout.size() <= isize::MAX，
        // 所以这里的 unwrap 永远不可能失败
        let new_layout = Layout::array::<T>(new_cap).unwrap();

        // 保证新申请的内存没有超出 `isize::MAX` 字节
        assert!(new_layout.size() <= isize::MAX as usize, "Allocation too large");

        let new_ptr = if self.cap == 0 {
            unsafe { alloc::alloc(new_layout) }
        } else {
            let old_layout = Layout::array::<T>(self.cap).unwrap();
            let old_ptr = self.ptr.as_ptr() as *mut u8;
            unsafe { alloc::realloc(old_ptr, old_layout, new_layout.size()) }
        };

        // 如果分配失败，`new_ptr` 就会成为空指针，我们需要对应 abort 的操作
        self.ptr = match NonNull::new(new_ptr as *mut T) {
            Some(p) => p,
            None => alloc::handle_alloc_error(new_layout),
        };
        self.cap = new_cap;
    }
}

impl<T> Drop for RawVec<T> {
    fn drop(&mut self) {
        if self.cap != 0 {
            let layout = Layout::array::<T>(self.cap).unwrap();
            unsafe {
                alloc::dealloc(self.ptr.as_ptr() as *mut u8, layout);
            }
        }
    }
}
```

随后，把 Vec 改成这样：

<!-- ignore: simplified code -->

```rust,ignore
pub struct Vec<T> {
    buf: RawVec<T>,
    len: usize,
}

impl<T> Vec<T> {
    fn ptr(&self) -> *mut T {
        self.buf.ptr.as_ptr()
    }

    fn cap(&self) -> usize {
        self.buf.cap
    }

    pub fn new() -> Self {
        Vec {
            buf: RawVec::new(),
            len: 0,
        }
    }

    // push/pop/insert/remove 这些操作做了小小的改变，如下所示:
    // * `self.ptr.as_ptr() -> self.ptr()`
    // * `self.cap -> self.cap()`
    // * `self.grow() -> self.buf.grow()`
}

impl<T> Drop for Vec<T> {
    fn drop(&mut self) {
        while let Some(_) = self.pop() {}
        // RawVec 来负责释放内存
    }
}
```

最后，我们可以把 IntoIter 改得相当简单：

<!-- ignore: simplified code -->

```rust,ignore
pub struct IntoIter<T> {
    _buf: RawVec<T>, // 我们实际上并不关心这个，只需要他们保证分配的空间不被释放
    start: *const T,
    end: *const T,
}

// next 和 next_back 保持不变，因为它们并没有用到 buf

impl<T> Drop for IntoIter<T> {
    fn drop(&mut self) {
        // 我们只需要确保 Vec 中所有元素都被读取了，
        // 在这之后这些元素会被自动清理
        for _ in &mut *self {}
    }
}

impl<T> IntoIterator for Vec<T> {
    type Item = T;
    type IntoIter = IntoIter<T>;
    fn into_iter(self) -> IntoIter<T> {
        // 需要使用 ptr::read 非安全地把 buf 移出，因为它没有实现 Copy，
        // 而且 Vec 实现了 Drop Trait (因此我们不能销毁它)
        let buf = unsafe { ptr::read(&self.buf) };
        let len = self.len;
        mem::forget(self);

        IntoIter {
            start: buf.ptr.as_ptr(),
            end: if buf.cap == 0 {
                // 不能通过这个指针获取偏移，除非已经分配了内存
                buf.ptr.as_ptr()
            } else {
                unsafe { buf.ptr.as_ptr().add(len) }
            },
            _buf: buf,
        }
    }
}
```

是不是好多了！
