# 处理零大小的类型

是时候了！我们将与 ZST（零大小类型）这个幽灵作斗争。安全的 Rust 从来不需要关心这个问题，但是 Vec 在原始指针和原始分配上非常密集，这正是需要关心零尺寸类型的两种情况。我们需要注意两件事：

- 如果你在分配大小上传入 0，原始分配器 API 有未定义的行为。
- 原始指针偏移量对于零大小的类型来说是无效的（no-ops），这将破坏我们的 C 风格指针迭代器。

幸好我们之前把指针迭代器和分配处理分别抽象为`RawValIter`和`RawVec`。现在回过头来看，多么的方便啊。

## 分配零大小的类型

那么，如果分配器 API 不支持零大小的分配，我们到底要把什么作为我们的分配来存储呢？当然是`NonNull::dangling()`! 几乎所有使用 ZST 的操作都是 no-op，因为 ZST 正好有且仅有一个值，因此在存储或加载它们时不需要考虑状态。这实际上延伸到了`ptr::read`和`ptr::write`：它们实际上根本不会去用指针。因此，我们从来不需要改变指针。

然而，请注意，我们之前对在溢出前耗尽内存的防御，在零大小的类型中不再有效了。我们必须明确地防止零大小类型的容量溢出。

由于我们目前的架构，这意味着要写 3 个边界处理，在`RawVec`的每个方法中都有一个：

<!-- ignore: simplified code -->

```rust,ignore
impl<T> RawVec<T> {
    fn new() -> Self {
        // !0 等价于 usize::MAX，这一段分支代码在编译期间就可以计算出结果返回的结果，返回给 cap
        let cap = if mem::size_of::<T>() == 0 { !0 } else { 0 };

        // `NonNull::dangling()` 有双重含义:
        // `未分配内存 (unallocated)`, `零尺寸 (zero-sized allocation)`
        RawVec {
            ptr: NonNull::dangling(),
            cap: cap,
            _marker: PhantomData,
        }
    }

    fn grow(&mut self) {
        // 因为当 T 的尺寸为 0 时我们设置了 cap 为 usize::MAX
        // 这一步成立意味着 Vec 溢出了
        assert!(mem::size_of::<T>() != 0, "capacity overflow");

        let (new_cap, new_layout) = if self.cap == 0 {
            (1, Layout::array::<T>(1).unwrap())
        } else {
            // 保证新申请的内存没有超出 `isize::MAX` 字节
            let new_cap = 2 * self.cap;

            // `Layout::array` 会检查申请的空间是否小于等于 usize::MAX，
            // 但是因为 old_layout.size() <= isize::MAX，
            // 所以这里的 unwrap 永远不可能失败
            let new_layout = Layout::array::<T>(new_cap).unwrap();
            (new_cap, new_layout)
        };

        // 保证新申请的内存没有超出 `isize::MAX` 字节
        assert!(new_layout.size() <= isize::MAX as usize, "Allocation too large");

        let new_ptr = if self.cap == 0 {
            unsafe { alloc::alloc(new_layout) }
        } else {
            let old_layout = Layout::array::<T>(self.cap).unwrap();
            let old_ptr = self.ptr.as_ptr() as *mut u8;
            unsafe { alloc::realloc(old_ptr, old_layout, new_layout.size()) }
        };

        // 如果分配失败，`new_ptr` 就会成为空指针，我们需要处理这个意外情况
        self.ptr = match NonNull::new(new_ptr as *mut T) {
            Some(p) => p,
            None => alloc::handle_alloc_error(new_layout),
        };
        self.cap = new_cap;
    }
}

impl<T> Drop for RawVec<T> {
    fn drop(&mut self) {
        let elem_size = mem::size_of::<T>();

        if self.cap != 0 && elem_size != 0 {
            unsafe {
                alloc::dealloc(
                    self.ptr.as_ptr() as *mut u8,
                    Layout::array::<T>(self.cap).unwrap(),
                );
            }
        }
    }
}
```

搞定！我们现在支持 push 和 pop 零大小类型。不过，我们的迭代器（不是由 slice Deref 提供的）仍然是一团浆糊。

## 迭代 ZST

零大小的偏移量是 no-op。这意味着我们目前的设计总是将`start`和`end`初始化为相同的值，而我们的迭代器将一无所获。目前的解决方案是将指针转为整数，增加，然后再转回。

<!-- ignore: simplified code -->

```rust,ignore
impl<T> RawValIter<T> {
    unsafe fn new(slice: &[T]) -> Self {
        RawValIter {
            start: slice.as_ptr(),
            end: if mem::size_of::<T>() == 0 {
                ((slice.as_ptr() as usize) + slice.len()) as *const _
            } else if slice.len() == 0 {
                slice.as_ptr()
            } else {
                slice.as_ptr().add(slice.len())
            },
        }
    }
}
```

现在，我们有了另一个 bug：我们的迭代器不再是完全不运行，而是现在的迭代器*永远*都在运行。我们需要在我们的迭代器 impls 中做同样的技巧。另外，我们的 size_hint 计算代码将对 ZST 除以 0。既然我们会把这两个指针当作是指向字节的，所以我们就把大小 0 映射到除以 1，这样的话`next`的代码如下：

<!-- ignore: simplified code -->

```rust,ignore
fn next(&mut self) -> Option<T> {
    if self.start == self.end {
        None
    } else {
        unsafe {
            let result = ptr::read(self.start);
            self.start = if mem::size_of::<T>() == 0 {
                (self.start as usize + 1) as *const _
            } else {
                self.start.offset(1)
            };
            Some(result)
        }
    }
}
```

你找到 bug 了嘛？没人看到！连最初的作者也是几年之后闲逛这个页面的时候，觉得这段代码比较可疑，因为这里直接滥用了迭代器的指针当作了 _计数器_，而这就使得了指针 _不对齐_！在使用 ZST 的时候，我们的工作之一就是必须保证指针对齐！_啊这_！

原始指针在任何时候都不需要对齐，所以使用指针作为计数器的基本技巧是 _没问题的_，但是当它们被传递给`ptr::read`时，它们 _应该_ 是对齐的! 这 _可能_ 是不必要的迂腐操作，因为`ptr::read`在处理 ZST 时其实是个 noop，但让我们稍微负责一点，当遇到 ZST 时从`NonNull::dangling`读取。

（或者你也可以在 ZST 路径上调用`read_unaligned`。两者都可以。因为无论哪种方式，我们都是在无中生有，而且都最终编译成 noop。）

<!-- ignore: simplified code -->

```rust,ignore
impl<T> Iterator for RawValIter<T> {
    type Item = T;
    fn next(&mut self) -> Option<T> {
        if self.start == self.end {
            None
        } else {
            unsafe {
                if mem::size_of::<T>() == 0 {
                    self.start = (self.start as usize + 1) as *const _;
                    Some(ptr::read(NonNull::<T>::dangling().as_ptr()))
                } else {
                    let old_ptr = self.start;
                    self.start = self.start.offset(1);
                    Some(ptr::read(old_ptr))
                }
            }
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let elem_size = mem::size_of::<T>();
        let len = (self.end as usize - self.start as usize)
                  / if elem_size == 0 { 1 } else { elem_size };
        (len, Some(len))
    }
}

impl<T> DoubleEndedIterator for RawValIter<T> {
    fn next_back(&mut self) -> Option<T> {
        if self.start == self.end {
            None
        } else {
            unsafe {
                if mem::size_of::<T>() == 0 {
                    self.end = (self.end as usize - 1) as *const _;
                    Some(ptr::read(NonNull::<T>::dangling().as_ptr()))
                } else {
                    self.end = self.end.offset(-1);
                    Some(ptr::read(self.end))
                }
            }
        }
    }
}
```

好啦，迭代器也搞定啦！
