# 析构

Rust 通过`Drop` trait 提供了完整的自动析构器，它提供了以下这个方法：

<!-- ignore: function header -->
```rust,ignore
fn drop(&mut self);
```

这个方法给了类型一些时间来完成它正在做的事情。

**在`drop`运行后，Rust 将递归地尝试删除`self`的所有字段。**

这是一个方便的功能，这样你就不必写“析构器模板”来丢弃子字段。如果一个结构除了丢弃其子字段之外没有特殊的丢弃逻辑，那么就意味着根本不需要实现`Drop`!

**在 Rust 1.0 中没有稳定的方法来阻止这种行为。**

请注意，这里使用的是`&mut self`，意味着即使你想要阻止递归的 Drop（例如将字段移出 self），Rust 也会阻止你。对于大多数类型来说，这完全没有问题。

一个自定义的`Box`的实现可以这样写`Drop`：

```rust
#![feature(ptr_internals, allocator_api)]

use std::alloc::{Allocator, Global, GlobalAlloc, Layout};
use std::mem;
use std::ptr::{drop_in_place, NonNull, Unique};

struct Box<T>{ ptr: Unique<T> }

impl<T> Drop for Box<T> {
    fn drop(&mut self) {
        unsafe {
            drop_in_place(self.ptr.as_ptr());
            let c: NonNull<T> = self.ptr.into();
            Global.deallocate(c.cast(), Layout::new::<T>())
        }
    }
}
# fn main() {}
```

这样做是可行的，因为当 Rust 去丢弃`ptr`字段时，它只是看到一个[Unique]，没有实际的`Drop`实现。同样的，没有任何东西可以在释放后使用`ptr`，因为当 drop 退出时，它就变得不可访问了。

然而下面这段代码就不可行了：

```rust
#![feature(allocator_api, ptr_internals)]

use std::alloc::{Allocator, Global, GlobalAlloc, Layout};
use std::ptr::{drop_in_place, Unique, NonNull};
use std::mem;

struct Box<T>{ ptr: Unique<T> }

impl<T> Drop for Box<T> {
    fn drop(&mut self) {
        unsafe {
            drop_in_place(self.ptr.as_ptr());
            let c: NonNull<T> = self.ptr.into();
            Global.deallocate(c.cast(), Layout::new::<T>());
        }
    }
}

struct SuperBox<T> { my_box: Box<T> }

impl<T> Drop for SuperBox<T> {
    fn drop(&mut self) {
        unsafe {
            // 释放 box 的内容，而不是 drop box 的内容
            let c: NonNull<T> = self.my_box.ptr.into();
            Global.deallocate(c.cast::<u8>(), Layout::new::<T>());
        }
    }
}
# fn main() {}
```

当我们在 SuperBox 的析构器中释放完`box`的 ptr 后，Rust 会很高兴地告诉 box 去 Drop 自己，然后，你就能开开心心去 debug use-after-free 和 double-free 的问题了。

请注意，递归 drop 行为适用于所有结构和枚举，无论它们是否实现了 Drop。因此，像这样的代码：


```rust
struct Boxy<T> {
    data1: Box<T>,
    data2: Box<T>,
    info: u32,
}
```

在它将被丢弃时，它的 data1 和 data2 的字段就会被析构，尽管它本身并没有实现 Drop。我们说这样的类型*需要 Drop*，尽管它本身不是 Drop。

类似地：

```rust
enum Link {
    Next(Box<Link>),
    None,
}
```

当且仅当一个实例存储了 Next 变量时，它的内部 Box 字段将被丢弃。

一般来说，这种设计非常好，因为当你重构数据布局时，你不需要担心添加/删除`Drop`的问题。当然，也有很多需要用析构器做更棘手的事情的例子。

经典的覆盖递归 drop 行为并允许在`drop`过程中移出 Self 的安全的解决方案是，使用一个 Option：

```rust
#![feature(allocator_api, ptr_internals)]

use std::alloc::{Allocator, GlobalAlloc, Global, Layout};
use std::ptr::{drop_in_place, Unique, NonNull};
use std::mem;

struct Box<T>{ ptr: Unique<T> }

impl<T> Drop for Box<T> {
    fn drop(&mut self) {
        unsafe {
            drop_in_place(self.ptr.as_ptr());
            let c: NonNull<T> = self.ptr.into();
            Global.deallocate(c.cast(), Layout::new::<T>());
        }
    }
}

struct SuperBox<T> { my_box: Option<Box<T>> }

impl<T> Drop for SuperBox<T> {
    fn drop(&mut self) {
        unsafe {
            // 释放 box 的内容，而不是 drop box 的内容，
            // 需要将 box 字段设置为 None，防止 Rust 对 box 成员可能存在的drop操作
            let my_box = self.my_box.take().unwrap();
            let c: NonNull<T> = my_box.ptr.into();
            Global.deallocate(c.cast(), Layout::new::<T>());
            mem::forget(my_box);
        }
    }
}
# fn main() {}
```

然而这有相当奇怪的语义：你是说一个*应该*总是 Some 的字段*可能*是 None，只是因为这发生在析构器中。当然，这也有一定的意义：你可以在析构器中调用 self 上的任意方法，这应该可以防止你在释放字段后这样做；而并不是说它能阻止你产生无效的状态。

总的来说，这是个可以接受的选择。当然，你应该在默认情况下达到这样的效果。然而，在未来，我们希望有一种更好的方式来指明一个字段不应该被自动 drop 掉。

[Unique]: phantom-data.html
