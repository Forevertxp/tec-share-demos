package com.tecshare.performance;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class Membership {
    private Membership() {}

    public static List<Long> listScan(List<Long> students, List<Long> selected) {
        List<Long> result = new ArrayList<>();
        for (Long id : students) if (selected.contains(id)) result.add(id);
        return result;
    }

    public static List<Long> buildSetPerRequest(List<Long> students, List<Long> selected) {
        return prebuiltSet(students, new HashSet<>(selected));
    }

    public static List<Long> prebuiltSet(List<Long> students, Set<Long> selected) {
        List<Long> result = new ArrayList<>();
        for (Long id : students) if (selected.contains(id)) result.add(id);
        return result;
    }
}
