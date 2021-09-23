# Deref

好了！我们已经实现了一个基本像样的栈。我们可以 push 和 pop，我们还可以自己 drop。然而，我们还需要一大堆的功能。特别是， 尽管我们有了一个合适的数组，但还没有切片的功能。这其实很容易解决：我们可以实现`Deref<Target=[T]>`。这将神奇地使我们的 Vec 在各种条件下强制成为一个切片，并且表现得像一个切片。

我们只需要`slice::from_raw_parts`。它将为我们正确处理空切片。之后当我们设置了零大小的类型支持，它也会对这些类型进行正确的处理。

<!-- ignore: simplified code -->
```rust,ignore
use std::ops::Deref;

impl<T> Deref for Vec<T> {
    type Target = [T];
    fn deref(&self) -> &[T] {
        unsafe {
            std::slice::from_raw_parts(self.ptr.as_ptr(), self.len)
        }
    }
}
```

还有 DerefMut：

<!-- ignore: simplified code -->
```rust,ignore
use std::ops::DerefMut;

impl<T> DerefMut for Vec<T> {
    fn deref_mut(&mut self) -> &mut [T] {
        unsafe {
            std::slice::from_raw_parts_mut(self.ptr.as_ptr(), self.len)
        }
    }
}
```

现在我们有了`len`、`first`、`last`、索引、切片、排序、`iter`、`iter_mut`，以及 slice 提供的其他各种功能啦！
