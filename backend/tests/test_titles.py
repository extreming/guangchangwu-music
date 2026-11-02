from app.services.titles import clean_title, filename_for


def test_keeps_song_name_and_drops_hashtags():
    assert clean_title("广场舞蹈《幸福舞步》教学 #广场舞 #中老年") == "广场舞蹈《幸福舞步》教学"


def test_strips_share_boilerplate():
    assert clean_title("复制打开抖音，看看【张三的作品】最炫民族风") == "最炫民族风"
    assert clean_title("7.64 aFu:/ 夕阳红广场舞") == "夕阳红广场舞"


def test_empty_and_length_and_filename():
    assert clean_title("") == "未命名音乐"
    assert clean_title("   ### ") == "未命名音乐"
    assert len(clean_title("舞" * 80)) == 48
    assert filename_for("夕阳红广场舞") == "夕阳红广场舞.mp3"
    assert "/" not in filename_for("a/b:c")
    assert ":" not in filename_for("a/b:c")
