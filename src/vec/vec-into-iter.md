# IntoIter

让我们继续，接下来写迭代器。`iter`和`iter_mut`已经为我们写好了，感谢 Deref 的魔法。然而，有两个有趣的迭代器是 Vec 提供的，而 slice 不能提供：`into_iter`和`drain`。

IntoIter 通过消耗掉 Vec 的值（获取 Vec 的所有权），并因此可以产生其元素的值（所有权）。为了实现这个目的，IntoIter 需要控制 Vec 的分配。

IntoIter 也需要是 DoubleEnded，以便能够从两端读取。从后面读取可以通过调用`pop`来实现，但是从前面读取就比较困难了。我们可以调用`remove(0)`，但这将是非常昂贵的。相反，我们将使用`ptr::read`来复制 Vec 两端的值，而不改变缓冲区。

为了做到这一点，我们将使用一个非常常见的 C 语言的数组迭代习惯。我们将建立两个指针；一个指向数组的开始，另一个指向数组结束后的一个元素。当我们想从一端获得一个元素时，我们将读出指向那一端的值，并将指针移到另一端。当这两个指针相等时，我们就知道我们已经完成了。

注意，对于`next`和`next_back`来说，读取和偏移的顺序是相反的。对于`next_back`来说，指针总是在它想读取的元素之后，而对于`next`来说，指针正好在它想读取的元素上。要想知道为什么会这样，请考虑除一个元素外的所有元素都已经产生的情况。

这个数组看起来像这样：

```text
          S  E
[X, X, X, O, X, X, X]
```

如果 E 直接指向它想产生的下一个元素，它将与没有更多元素可以产生的情况没有区别。

虽然我们在迭代过程中实际上并不关心它，但我们也需要保留 Vec 的分配信息，以便在 IntoIter 被丢弃后释放它。

所以我们将使用下面的结构。

<!-- ignore: simplified code -->

```rust,ignore
pub struct IntoIter<T> {
    buf: NonNull<T>,
    cap: usize,
    start: *const T,
    end: *const T,
}
```

而这就是我们最终的初始化结果：

<!-- ignore: simplified code -->

```rust,ignore
impl<T> IntoIterator for Vec<T> {
    type Item = T;
    type IntoIter = IntoIter<T>;
    fn into_iter(self) -> IntoIter<T> {
        // 确保 Vec 不会被 drop，因为那样会释放内存
        let vec = ManuallyDrop::new(self);

        // 因为 Vec 实现了 Drop，所以我们不能销毁它
        let ptr = vec.ptr;
        let cap = vec.cap;
        let len = vec.len;

        IntoIter {
            buf: ptr,
            cap,
            start: ptr.as_ptr(),
            end: if cap == 0 {
                // 不能通过这个指针获取偏移，因为没有分配内存
                ptr.as_ptr()
            } else {
                unsafe { ptr.as_ptr().add(len) }
            },
        }
    }
}
```

向前迭代：

<!-- ignore: simplified code -->

```rust,ignore
impl<T> Iterator for IntoIter<T> {
    type Item = T;
    fn next(&mut self) -> Option<T> {
        if self.start == self.end {
            None
        } else {
            unsafe {
                let result = ptr::read(self.start);
                self.start = self.start.offset(1);
                Some(result)
            }
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let len = (self.end as usize - self.start as usize)
                  / mem::size_of::<T>();
        (len, Some(len))
    }
}
```

向后迭代：

<!-- ignore: simplified code -->

```rust,ignore
impl<T> DoubleEndedIterator for IntoIter<T> {
    fn next_back(&mut self) -> Option<T> {
        if self.start == self.end {
            None
        } else {
            unsafe {
                self.end = self.end.offset(-1);
                Some(ptr::read(self.end))
            }
        }
    }
}
```

因为 IntoIter 拥有其分配的所有权，它需要实现 Drop 来释放它；并且，它也需要在 Drop 里丢弃它所包含的任何没有被迭代到的元素。

<!-- ignore: simplified code -->

```rust,ignore
impl<T> Drop for IntoIter<T> {
    fn drop(&mut self) {
        if self.cap != 0 {
            // 将剩下的元素 drop
            for _ in &mut *self {}
            let layout = Layout::array::<T>(self.cap).unwrap();
            unsafe {
                alloc::dealloc(self.buf.as_ptr() as *mut u8, layout);
            }
        }
    }
}
```
