package com.tecshare.performance;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class MembershipTest {
    private void compare(List<Long> students, List<Long> selected, List<Long> expected) {
        var studentsBefore = new ArrayList<>(students);
        var selectedBefore = new ArrayList<>(selected);
        assertEquals(expected, Membership.listScan(students, selected));
        assertEquals(expected, Membership.buildSetPerRequest(students, selected));
        assertEquals(expected, Membership.prebuiltSet(students, new HashSet<>(selected)));
        assertEquals(studentsBefore, students);
        assertEquals(selectedBefore, selected);
    }
    @Test void keepsStudentOrderAndStudentDuplicates() {
        compare(List.of(3L, 1L, 3L, 2L), List.of(3L, 3L, 1L), List.of(3L, 1L, 3L));
    }
    @Test void permitsNullMembershipLikeArrayList() {
        compare(Arrays.asList(null, 1L, 2L, null), Arrays.asList(null, 1L), Arrays.asList(null, 1L, null));
    }
    @Test void emptyStudents() { compare(List.of(), List.of(1L), List.of()); }
    @Test void emptySelection() { compare(List.of(1L), List.of(), List.of()); }
    @Test void noHits() { compare(List.of(1L, 2L), List.of(3L), List.of()); }
    @Test void randomizedInputsRetainTheSameOrderedOutput() {
        Random random = new Random(279);
        for (int sample = 0; sample < 100; sample++) {
            List<Long> students = new ArrayList<>(), selected = new ArrayList<>();
            for (int i = 0; i < 50; i++) students.add((long) random.nextInt(30));
            for (int i = 0; i < 20; i++) selected.add((long) random.nextInt(30));
            compare(students, selected, Membership.listScan(students, selected));
        }
    }
}
