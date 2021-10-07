# Send 和 Sync

并不是所有的东西都服从于继承的可变性。有些类型允许你在内存中对一个位置有多个别名，并且同时修改它。除非这些类型使用同步手段来管理这种访问，否则它们绝对不是线程安全的。Rust 通过 `Send`和`Sync` Trait 来解决这个问题：

* 如果将一个类型发送到另一个线程是安全的，那么它就是`Send`
* 如果一个类型可以安全地在线程间共享，那么它就是`Sync`的（当且仅当`&T`是`Send`时，`T`是`Sync`的）

Send 和 Sync 是 Rust 的并发故事的基础。因此，存在大量的特殊工具来使它们正常工作。首先，它们是[不安全的 Trait][unsafe traits],这意味着它们的实现是不安全的，而其他不安全的代码可以认为它们是正确实现的。由于它们是*标记特性*（它们没有像方法那样的相关项目），正确实现仅仅意味着它们具有实现者应该具有的内在属性。不正确地实现 Send 或 Sync 会导致未定义行为。

Send 和 Sync 也是自动派生的 Trait。这意味着，与其它 Trait 不同，如果一个类型完全由 Send 或 Sync 类型组成，那么它就是 Send 或 Sync。几乎所有的基本数据类型都是`Send`和`Sync`，因此，几乎所有你将与之交互的类型都是`Send`和`Sync`。

主要的例外情况包括：

* 原始指针既不是 Send 也不是 Sync（因为它们没有安全防护）
* `UnsafeCell`不是 Sync 的（因此`Cell`和`RefCell`也不是）
* `Rc`不是 Send 或 Sync 的（因为 Refcount 是共享的、不同步的）

`Rc`和`UnsafeCell`从根本上说不是线程安全的：它们共享了非同步的可变状态。然而，严格来说，原始指针被标记为线程不安全，更像是一个*提示*。用原始指针做任何有用的事情都需要对其进行解引用，这已经是不安全的了；当然，从这个角度上说，人们也可以认为将它们标记为线程安全的做法也没啥问题。

然而，更重要的是，它们不是线程安全的，是为了防止包含它们的类型被自动标记为线程安全的。这些类型的所有权并不明确，它们的作者也不太可能认真考虑线程安全问题。在`Rc`的例子中，我们有一个很好的例子，它包含一个绝对不是线程安全的`*mut`类型。

如果需要的话，那些没有自动派生的类型可以很简单地实现它们：

```rust
struct MyBox(*mut u8);

unsafe impl Send for MyBox {}
unsafe impl Sync for MyBox {}
```

在*难以置信*的罕见情况下，一个类型被不恰当地自动派生为 Send 或 Sync，那么我们也可以不实现 Send 和 Sync：

```rust
#![feature(negative_impls)]

// I have some magic semantics for some synchronization primitive!
struct SpecialThreadToken(u8);

impl !Send for SpecialThreadToken {}
impl !Sync for SpecialThreadToken {}
```

请注意，*正常情况下*是不可能错误地派生出 Send 和 Sync 的。只有那些被其他不安全代码赋予特殊意义的类型才有可能因为不正确的 Send 或 Sync 而造成麻烦。

大多数对原始指针的使用应该被封装在一个足够的抽象后面，以便 Send 和 Sync 可以被派生。例如，所有 Rust 的标准集合都是 Send 和 Sync（当它们包含 Send 和 Sync 类型时），尽管它们普遍使用原始指针来管理内存分配和复杂的所有权。同样的，大多数这些集合的迭代器都是 Send 和 Sync 的，因为它们在很大程度上表现得像集合的`&`或`&mut`。

## 示例

[`Box`][box-doc]由于[各种原因][box-is-special]，编译器将其作为自己的特殊内建类型来实现，但是我们可以自己实现一些具有类似行为的东西，来看看什么时候实现 Send 和 Sync 是合理的。让我们把它叫做`Carton`。

我们先写代码，把分配在栈上的一个值，转移到堆上：

```rust
# pub mod libc {
#    pub use ::std::os::raw::{c_int, c_void};
#    #[allow(non_camel_case_types)]
#    pub type size_t = usize;
#    extern "C" { pub fn posix_memalign(memptr: *mut *mut c_void, align: size_t, size: size_t) -> c_int; }
# }
use std::{
    mem::{align_of, size_of},
    ptr,
};

struct Carton<T>(ptr::NonNull<T>);

impl<T> Carton<T> {
    pub fn new(value: T) -> Self {
        // Allocate enough memory on the heap to store one T.
        assert_ne!(size_of::<T>(), 0, "Zero-sized types are out of the scope of this example");
        let mut memptr: *mut T = ptr::null_mut();
        unsafe {
            let ret = libc::posix_memalign(
                (&mut memptr).cast(),
                align_of::<T>(),
                size_of::<T>()
            );
            assert_eq!(ret, 0, "Failed to allocate or invalid alignment");
        };

        // NonNull is just a wrapper that enforces that the pointer isn't null.
        let ptr = {
            // Safety: memptr is dereferenceable because we created it from a
            // reference and have exclusive access.
            ptr::NonNull::new(memptr)
                .expect("Guaranteed non-null if posix_memalign returns 0")
        };

        // Move value from the stack to the location we allocated on the heap.
        unsafe {
            // Safety: If non-null, posix_memalign gives us a ptr that is valid
            // for writes and properly aligned.
            ptr.as_ptr().write(value);
        }

        Self(ptr)
    }
}
```

这不是很有用，因为一旦我们的用户给了我们一个值，他们就没有办法访问它。[`Box`][box-doc]实现了[`Deref`][deref-doc]和[`DerefMut`][deref-mut-doc]，这样你就可以访问内部的值。让我们来做这件事：

```rust
use std::ops::{Deref, DerefMut};

# struct Carton<T>(std::ptr::NonNull<T>);
#
impl<T> Deref for Carton<T> {
    type Target = T;

    fn deref(&self) -> &Self::Target {
        unsafe {
            // Safety: The pointer is aligned, initialized, and dereferenceable
            //   by the logic in [`Self::new`]. We require writers to borrow the
            //   Carton, and the lifetime of the return value is elided to the
            //   lifetime of the input. This means the borrow checker will
            //   enforce that no one can mutate the contents of the Carton until
            //   the reference returned is dropped.
            self.0.as_ref()
        }
    }
}

impl<T> DerefMut for Carton<T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        unsafe {
            // Safety: The pointer is aligned, initialized, and dereferenceable
            //   by the logic in [`Self::new`]. We require writers to mutably
            //   borrow the Carton, and the lifetime of the return value is
            //   elided to the lifetime of the input. This means the borrow
            //   checker will enforce that no one else can access the contents
            //   of the Carton until the mutable reference returned is dropped.
            self.0.as_mut()
        }
    }
}
```

最后，让我们考虑一下我们的`Carton`是否是 Send 和 Sync。一些东西可以安全地成为 Send，除非它与其他东西共享可变的状态，而不对其实施排他性访问。每个`Carton`都有一个唯一的指针，所以我们可以标记为 Send：

```rust
# struct Carton<T>(std::ptr::NonNull<T>);
// Safety: No one besides us has the raw pointer, so we can safely transfer the
// Carton to another thread if T can be safely transferred.
unsafe impl<T> Send for Carton<T> where T: Send {}
```

那么 Sync 呢？为了使`Carton`能够 Sync，我们必须强制规定，你不能对存储在一个`Carton`中的东西进行写入，而这个东西可以从另一个`Carton`中读出或写入。因为你需要一个`&mut Carton`来写指针，并且借用检查器强制要求可变引用必须是排他的，所以把`Carton`标记为`Sync`也没啥问题：

```rust
# struct Carton<T>(std::ptr::NonNull<T>);
// Safety: Since there exists a public way to go from a `&Carton<T>` to a `&T`
// in an unsynchronized fashion (such as `Deref`), then `Carton<T>` can't be
// `Sync` if `T` isn't.
// Conversely, `Carton` itself does not use any interior mutability whatsoever:
// all the mutations are performed through an exclusive reference (`&mut`). This
// means it suffices that `T` be `Sync` for `Carton<T>` to be `Sync`:
unsafe impl<T> Sync for Carton<T> where T: Sync  {}
```

当我们断言我们的类型是 Send 和 Sync 时，我们通常需要强制要求每个包含的类型都是 Send 和 Sync。当编写行为像标准库类型的自定义类型时，我们可以断言我们有相同的要求。例如，下面的代码断言，如果同类的 Box 是 Send，那么 Carton 就是 Send —— 在这种情况下，这就等于说 T 是 Send：

```rust
# struct Carton<T>(std::ptr::NonNull<T>);
unsafe impl<T> Send for Carton<T> where Box<T>: Send {}
```

现在`Carton<T>`有一个内存泄漏，因为它从未释放它分配的内存。一旦我们解决了这个问题，我们就必须确保满足 Send 的新要求：我们需要确认`free`释放由另一个线程的分配产生的指针。我们可以在[`libc::free`][libc-freedocs]的文档中来确认这么做是可行的。

```rust
# struct Carton<T>(std::ptr::NonNull<T>);
# mod libc {
#     pub use ::std::os::raw::c_void;
#     extern "C" { pub fn free(p: *mut c_void); }
# }
impl<T> Drop for Carton<T> {
    fn drop(&mut self) {
        unsafe {
            libc::free(self.0.as_ptr().cast());
        }
    }
}
```

一个不会发生这种情况的好例子是 MutexGuard：注意[它不是 Send][mutex-guard-not-send-docs-rs]。MutexGuard 的实现[使用的库][mutex-guard-not-send-comment]要求你确保不会释放你在不同线程中获得的锁。如果你能够将 MutexGuard 发送到另一个线程，那么析构器就会在新的线程中运行，这就违反了该要求。但 MutexGuard 仍然可以是 Sync，因为你能发送给另一个线程的只是一个`&MutexGuard`，丢弃一个引用并没有什么作用。

TODO: 更好地解释什么可以或不可以是 Send 或 Sync。仅仅针对数据竞争就足够了？

[unsafe traits]: safe-unsafe-meaning.html
[box-doc]: https://doc.rust-lang.org/std/boxed/struct.Box.html
[box-is-special]: https://manishearth.github.io/blog/2017/01/10/rust-tidbits-box-is-special/
[deref-doc]: https://doc.rust-lang.org/core/ops/trait.Deref.html
[deref-mut-doc]: https://doc.rust-lang.org/core/ops/trait.DerefMut.html
[mutex-guard-not-send-docs-rs]: https://doc.rust-lang.org/std/sync/struct.MutexGuard.html#impl-Send
[mutex-guard-not-send-comment]: https://github.com/rust-lang/rust/issues/23465#issuecomment-82730326
[libc-free-docs]: https://linux.die.net/man/3/free
