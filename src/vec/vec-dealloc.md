# 释放内存

接下来我们应该实现 Drop，这样我们就不会大规模地泄漏大量的资源。最简单的方法是直接调用`pop`，直到它产生 None，然后再释放我们的 buffer。注意，如果`T: !Drop`的话，调用`pop`是不需要的。理论上，我们可以询问 Rust 是否`T` `need_drop`并省略对`pop`的调用。然而在实践中，LLVM 在做类似这样的简单的无副作用的删除代码方面*非常*好，所以我就省得麻烦了，除非你注意到它没有被优化掉（在这种情况下它被优化了）。

要注意的是，当`self.cap == 0`时，我们不能调用`alloc::dealloc`，因为在这种情况下我们实际上没有分配任何内存。

<!-- ignore: simplified code -->
```rust,ignore
impl<T> Drop for Vec<T> {
    fn drop(&mut self) {
        if self.cap != 0 {
            while let Some(_) = self.pop() { }
            let layout = Layout::array::<T>(self.cap).unwrap();
            unsafe {
                alloc::dealloc(self.ptr.as_ptr() as *mut u8, layout);
            }
        }
    }
}
```
