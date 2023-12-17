# Drain

接下来，让我们来实现 Drain。 Drain 与 IntoIter 大体上相同，只是它不是消耗 Vec，而是借用 Vec，并且不会修改到其分配。现在我们只实现“基本”的全范围版本。

<!-- ignore: simplified code -->

```rust,ignore
use std::marker::PhantomData;

struct Drain<'a, T: 'a> {
    // 这里需要限制生命周期, 因此我们使用了 `&'a mut Vec<T>`，
    // 也就是我们语义上包含的内容，
    // 我们只会调用 `pop()` 和 `remove(0)` 两个方法
    vec: PhantomData<&'a mut Vec<T>>,
    start: *const T,
    end: *const T,
}

impl<'a, T> Iterator for Drain<'a, T> {
    type Item = T;
    fn next(&mut self) -> Option<T> {
        if self.start == self.end {
            None
```

——等等，这看着好像很眼熟？IntoIter 和 Drain 有完全相同的结构，让我们再做一些抽象：

<!-- ignore: simplified code -->

```rust,ignore
struct RawValIter<T> {
    start: *const T,
    end: *const T,
}

impl<T> RawValIter<T> {
    // 构建 RawValIter 是不安全的，因为它没有关联的生命周期，
    // 将 RawValIter 存储在与它实际分配相同的结构体中是非常有必要的，
    // 但这里是具体的实现细节，不用对外公开
    unsafe fn new(slice: &[T]) -> Self {
        RawValIter {
            start: slice.as_ptr(),
            end: if slice.len() == 0 {
                // 如果 `len = 0`, 说明没有分配内存，需要避免使用 offset，
                // 因为那样会给 LLVM 的 GEP 传递错误的信息
                slice.as_ptr()
            } else {
                slice.as_ptr().add(slice.len())
            }
        }
    }
}

// Iterator 和 DoubleEndedIterator 和 IntoIter 实现起来很类似
```

IntoIter 我们可以改成这样：

<!-- ignore: simplified code -->

```rust,ignore
pub struct IntoIter<T> {
    _buf: RawVec<T>,
    iter: RawValIter<T>,
}

impl<T> Iterator for IntoIter<T> {
    type Item = T;
    fn next(&mut self) -> Option<T> { self.iter.next() }
    fn size_hint(&self) -> (usize, Option<usize>) { self.iter.size_hint() }
}

impl<T> DoubleEndedIterator for IntoIter<T> {
    fn next_back(&mut self) -> Option<T> { self.iter.next_back() }
}

impl<T> Drop for IntoIter<T> {
    fn drop(&mut self) {
        for _ in &mut *self {}
    }
}

impl<T> IntoIterator for Vec<T> {
    type Item = T;
    type IntoIter = IntoIter<T>;
    fn into_iter(self) -> IntoIter<T> {
        unsafe {
            let iter = RawValIter::new(&self);

            let buf = ptr::read(&self.buf);
            mem::forget(self);

            IntoIter {
                iter,
                _buf: buf,
            }
        }
    }
}
```

请注意，我在这个设计中留下了一些奇怪之处，以使升级 Drain 来处理任意的子范围更容易一些。特别是我们*可以*让 RawValIter 在 drop 时 drain 自身，但这对更复杂的 Drain 来说是不合适的。我们还使用了一个 slice 来简化 Drain 的初始化。

好了，现在实现 Drain 真的很容易了：

<!-- ignore: simplified code -->

```rust,ignore
use std::marker::PhantomData;

pub struct Drain<'a, T: 'a> {
    vec: PhantomData<&'a mut Vec<T>>,
    iter: RawValIter<T>,
}

impl<'a, T> Iterator for Drain<'a, T> {
    type Item = T;
    fn next(&mut self) -> Option<T> { self.iter.next() }
    fn size_hint(&self) -> (usize, Option<usize>) { self.iter.size_hint() }
}

impl<'a, T> DoubleEndedIterator for Drain<'a, T> {
    fn next_back(&mut self) -> Option<T> { self.iter.next_back() }
}

impl<'a, T> Drop for Drain<'a, T> {
    fn drop(&mut self) {
        for _ in &mut *self {}
    }
}

impl<T> Vec<T> {
    pub fn drain(&mut self) -> Drain<T> {
        let iter = unsafe { RawValIter::new(&self) };

        // 这里事关 mem::forget 的安全。
        // 如果 Drain 被 forget，我们就会泄露整个 Vec 的内存，
        // 既然我们始终要做这一步，为何不在这里完成呢？
        self.len = 0;

        Drain {
            iter: iter,
            vec: PhantomData,
        }
    }
}
```

关于`mem::forget`问题的更多细节，参见[关于泄漏的章节][leaks]。

[leaks]: ../leaking.html
