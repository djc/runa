%str = type { i64, i8* }
%intiter = type { i64, i64, i64 }

declare void @print(%str* %s)
declare void @bool.__str__(i1 %v, %str* %s)
declare void @bool.__eq__(i1 %a, i1 %b, i1* %res)
declare void @int.__str__(i64 %n, %str* %s)
declare void @int.__bool__(i64 %n, i1* %res)
declare void @int.__eq__(i64 %a, i64 %b, i1* %res)
declare void @str.__bool__(%str* %s, i1* %res)
declare void @argv(i32 %argc, i8** %argv, %str** %out)
declare void @range(i64 %start, i64 %stop, i64 %step, %intiter* %res)
declare i1 @intiter.__next__(%intiter* %self, i64* %res)
