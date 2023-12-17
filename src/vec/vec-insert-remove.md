# 插入和删除

slice *不*提供的东西是`insert`和`remove`，所以我们接下来做这些。

insert 需要将目标索引的所有元素向右移动一个。要做到这一点，我们需要使用`ptr::copy`，它是 C 语言`memmove`的 Rust 版本。它将一些内存块从一个位置复制到另一个位置，正确处理源和目标重叠的情况（这在这里肯定会发生）。

如果我们在索引`i`处插入，我们要使用旧的 len 将`[i ... len]`转移到`[i+1 ... len+1]`。

<!-- ignore: simplified code -->
```rust,ignore
pub fn insert(&mut self, index: usize, elem: T) {
    // 注意：`<=` 是因为我们可以把值插入到任何索引范围 ([0,length-1]) 内的位置之后
    // 这种情况等同于 push
    assert!(index <= self.len, "index out of bounds");
    if self.len == self.cap { self.grow(); }

    unsafe {
        // ptr::copy(src, dest, len) 的含义： "从 src 复制连续的 len 个元素到 dst "
        ptr::copy(
            self.ptr.as_ptr().add(index),
            self.ptr.as_ptr().add(index + 1),
            self.len - index,
        );
        ptr::write(self.ptr.as_ptr().add(index), elem);
    }

    self.len += 1;
}
```

remove 的行为方式正好相反。我们需要将所有的元素从`[i+1 ... len + 1]`转移到`[i ... len]`，使用*新的* len。

<!-- ignore: simplified code -->
```rust,ignore
pub fn remove(&mut self, index: usize) -> T {
    // 注意：使用 `<` 是因为 index 不能删除超出元素下标的范围
    assert!(index < self.len, "index out of bounds");
    unsafe {
        self.len -= 1;
        let result = ptr::read(self.ptr.as_ptr().add(index));
        ptr::copy(
            self.ptr.as_ptr().add(index + 1),
            self.ptr.as_ptr().add(index),
            self.len - index,
        );
        result
    }
}
```
