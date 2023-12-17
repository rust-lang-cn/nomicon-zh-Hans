# 最终的代码

```rust
use std::alloc::{self, Layout};
use std::marker::PhantomData;
use std::mem;
use std::ops::{Deref, DerefMut};
use std::ptr::{self, NonNull};

struct RawVec<T> {
    ptr: NonNull<T>,
    cap: usize,
}

unsafe impl<T: Send> Send for RawVec<T> {}
unsafe impl<T: Sync> Sync for RawVec<T> {}

impl<T> RawVec<T> {
    fn new() -> Self {
        // !0 等价于 usize::MAX， 这一段分支代码在编译期间就可以计算出结果返回的结果，返回给 cap
        let cap = if mem::size_of::<T>() == 0 { !0 } else { 0 };

        // `NonNull::dangling()` 有双重含义:
        // `未分配内存 (unallocated)`, `零尺寸 (zero-sized allocation)`
        RawVec {
            ptr: NonNull::dangling(),
            cap: cap,
        }
    }

    fn grow(&mut self) {
        // 因为当 T 的尺寸为 0 时，我们设置了 cap 为 usize::MAX，
        // 这一步成立便意味着 Vec 溢出了.
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
        assert!(
            new_layout.size() <= isize::MAX as usize,
            "Allocation too large"
        );

        let new_ptr = if self.cap == 0 {
            unsafe { alloc::alloc(new_layout) }
        } else {
            let old_layout = Layout::array::<T>(self.cap).unwrap();
            let old_ptr = self.ptr.as_ptr() as *mut u8;
            unsafe { alloc::realloc(old_ptr, old_layout, new_layout.size()) }
        };

        // 如果分配失败，`new_ptr` 就会成为空指针，我们需要处理该意外情况
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
    pub fn push(&mut self, elem: T) {
        if self.len == self.cap() {
            self.buf.grow();
        }

        unsafe {
            ptr::write(self.ptr().add(self.len), elem);
        }

        // 不会溢出，会先 OOM
        self.len += 1;
    }

    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            None
        } else {
            self.len -= 1;
            unsafe { Some(ptr::read(self.ptr().add(self.len))) }
        }
    }

    pub fn insert(&mut self, index: usize, elem: T) {
        assert!(index <= self.len, "index out of bounds");
        if self.len == self.cap() {
            self.buf.grow();
        }

        unsafe {
            ptr::copy(
                self.ptr().add(index),
                self.ptr().add(index + 1),
                self.len - index,
            );
            ptr::write(self.ptr().add(index), elem);
        }

        self.len += 1;
    }

    pub fn remove(&mut self, index: usize) -> T {
        assert!(index < self.len, "index out of bounds");

        self.len -= 1;

        unsafe {
            let result = ptr::read(self.ptr().add(index));
            ptr::copy(
                self.ptr().add(index + 1),
                self.ptr().add(index),
                self.len - index,
            );
            result
        }
    }

    pub fn drain(&mut self) -> Drain<T> {
        let iter = unsafe { RawValIter::new(&self) };

        // 这里事关 mem::forget 的安全。
        // 如果 Drain 被 forget，我们就会泄露整个 Vec 的内存
        // 既然我们始终要做这一步，为何不在这里完成呢？
        self.len = 0;

        Drain {
            iter: iter,
            vec: PhantomData,
        }
    }
}

impl<T> Drop for Vec<T> {
    fn drop(&mut self) {
        while let Some(_) = self.pop() {}
        // RawVec 来负责释放内存
    }
}

impl<T> Deref for Vec<T> {
    type Target = [T];
    fn deref(&self) -> &[T] {
        unsafe { std::slice::from_raw_parts(self.ptr(), self.len) }
    }
}

impl<T> DerefMut for Vec<T> {
    fn deref_mut(&mut self) -> &mut [T] {
        unsafe { std::slice::from_raw_parts_mut(self.ptr(), self.len) }
    }
}

impl<T> IntoIterator for Vec<T> {
    type Item = T;
    type IntoIter = IntoIter<T>;
    fn into_iter(self) -> IntoIter<T> {
        let (iter, buf) = unsafe {
            (RawValIter::new(&self), ptr::read(&self.buf))
        };

        mem::forget(self);

        IntoIter {
            iter: iter,
            _buf: buf,
        }
    }
}

struct RawValIter<T> {
    start: *const T,
    end: *const T,
}

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

pub struct IntoIter<T> {
    _buf: RawVec<T>,    // 我们实际上并不关心这个，只需要他们保证分配的空间不被释放
    iter: RawValIter<T>,
}

impl<T> Iterator for IntoIter<T> {
    type Item = T;
    fn next(&mut self) -> Option<T> {
        self.iter.next()
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        self.iter.size_hint()
    }
}

impl<T> DoubleEndedIterator for IntoIter<T> {
    fn next_back(&mut self) -> Option<T> {
        self.iter.next_back()
    }
}

impl<T> Drop for IntoIter<T> {
    fn drop(&mut self) {
        for _ in &mut *self {}
    }
}

pub struct Drain<'a, T: 'a> {
    vec: PhantomData<&'a mut Vec<T>>,
    iter: RawValIter<T>,
}

impl<'a, T> Iterator for Drain<'a, T> {
    type Item = T;
    fn next(&mut self) -> Option<T> {
        self.iter.next()
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        self.iter.size_hint()
    }
}

impl<'a, T> DoubleEndedIterator for Drain<'a, T> {
    fn next_back(&mut self) -> Option<T> {
        self.iter.next_back()
    }
}

impl<'a, T> Drop for Drain<'a, T> {
    fn drop(&mut self) {
        // 消耗drain
        for _ in &mut *self {}
    }
}
#
# fn main() {
#     tests::create_push_pop();
#     tests::iter_test();
#     tests::test_drain();
#     tests::test_zst();
#     println!("All tests finished OK");
# }
#
# mod tests {
#     use super::*;
#
#     pub fn create_push_pop() {
#         let mut v = Vec::new();
#         v.push(1);
#         assert_eq!(1, v.len());
#         assert_eq!(1, v[0]);
#         for i in v.iter_mut() {
#             *i += 1;
#         }
#         v.insert(0, 5);
#         let x = v.pop();
#         assert_eq!(Some(2), x);
#         assert_eq!(1, v.len());
#         v.push(10);
#         let x = v.remove(0);
#         assert_eq!(5, x);
#         assert_eq!(1, v.len());
#     }
#
#     pub fn iter_test() {
#         let mut v = Vec::new();
#         for i in 0..10 {
#             v.push(Box::new(i))
#         }
#         let mut iter = v.into_iter();
#         let first = iter.next().unwrap();
#         let last = iter.next_back().unwrap();
#         drop(iter);
#         assert_eq!(0, *first);
#         assert_eq!(9, *last);
#     }
#
#     pub fn test_drain() {
#         let mut v = Vec::new();
#         for i in 0..10 {
#             v.push(Box::new(i))
#         }
#         {
#             let mut drain = v.drain();
#             let first = drain.next().unwrap();
#             let last = drain.next_back().unwrap();
#             assert_eq!(0, *first);
#             assert_eq!(9, *last);
#         }
#         assert_eq!(0, v.len());
#         v.push(Box::new(1));
#         assert_eq!(1, *v.pop().unwrap());
#     }
#
#     pub fn test_zst() {
#         let mut v = Vec::new();
#         for _i in 0..10 {
#             v.push(())
#         }
#
#         let mut count = 0;
#
#         for _ in v.into_iter() {
#             count += 1
#         }
#
#         assert_eq!(10, count);
#     }
# }
```
